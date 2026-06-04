import asyncio
import time
from dataclasses import dataclass, field
from decimal import Decimal


class ClockEstimator:
    """Per-exchange EWMA of clock offset (local_ms - exchange_ms)."""

    def __init__(self, alpha: float = 0.1):
        self._alpha = alpha
        self._offset_ms: float | None = None

    @property
    def offset_ms(self) -> float:
        return self._offset_ms if self._offset_ms is not None else 0.0

    def update(self, local_ms: float, exchange_ms: float) -> float:
        sample = local_ms - exchange_ms
        if self._offset_ms is None:
            self._offset_ms = sample
        else:
            self._offset_ms = self._alpha * sample + (1 - self._alpha) * self._offset_ms
        return self._offset_ms


@dataclass
class ExchangePrice:
    exchange: str
    symbol: str
    best_bid: Decimal
    best_ask: Decimal
    exchange_timestamp: int
    local_receive_time: float
    clock_offset_ms: float
    is_stale: bool = False


class PriceTable:
    """Lock-protected in-memory price table with timestamp alignment and staleness detection."""

    def __init__(self, stale_threshold_ms: float = 5000.0, clock_alpha: float = 0.1):
        self._lock = asyncio.Lock()
        self._prices: dict[str, ExchangePrice] = {}
        self._clocks: dict[str, ClockEstimator] = {}
        self._stale_threshold_ms = stale_threshold_ms
        self._clock_alpha = clock_alpha

    async def update(self, exchange: str, symbol: str, best_bid: Decimal,
                     best_ask: Decimal, exchange_ts: int) -> None:
        async with self._lock:
            now_ms = time.time() * 1000
            if exchange not in self._clocks:
                self._clocks[exchange] = ClockEstimator(alpha=self._clock_alpha)
            offset = self._clocks[exchange].update(now_ms, float(exchange_ts))
            self._prices[exchange] = ExchangePrice(
                exchange=exchange,
                symbol=symbol,
                best_bid=best_bid,
                best_ask=best_ask,
                exchange_timestamp=exchange_ts,
                local_receive_time=time.time(),
                clock_offset_ms=offset,
                is_stale=False,
            )

    async def get_valid_prices(self) -> dict[str, ExchangePrice]:
        async with self._lock:
            now_ms = time.time() * 1000
            valid = {}
            for name, price in self._prices.items():
                if price.is_stale:
                    continue
                adjusted_age = now_ms - (price.exchange_timestamp + price.clock_offset_ms)
                if adjusted_age > self._stale_threshold_ms:
                    price.is_stale = True
                else:
                    valid[name] = price
            return valid

    async def get_all_prices(self) -> dict[str, ExchangePrice]:
        async with self._lock:
            return dict(self._prices)

    async def get_stale_exchanges(self) -> list[str]:
        async with self._lock:
            now_ms = time.time() * 1000
            stale = []
            for name, price in self._prices.items():
                if price.is_stale:
                    stale.append(name)
                    continue
                adjusted_age = now_ms - (price.exchange_timestamp + price.clock_offset_ms)
                if adjusted_age > self._stale_threshold_ms:
                    stale.append(name)
            return stale

    async def mark_exchange_stale(self, exchange: str) -> None:
        async with self._lock:
            if exchange in self._prices:
                self._prices[exchange].is_stale = True
