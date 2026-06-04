import asyncio
import time
import statistics
from collections import deque
from dataclasses import dataclass
from decimal import Decimal


class SlidingWindowClockEstimator:
    """Sliding window median clock estimator with reset on stable burst."""

    def __init__(self, window_size: int = 20, stable_count: int = 5,
                 stale_discard_ms: float = 2000.0):
        self._window_size = window_size
        self._window: deque[float] = deque(maxlen=window_size)
        self._offset_ms: float = 0.0
        self._stable_count = stable_count
        self._stale_discard_ms = stale_discard_ms
        self._recent_diffs: deque[float] = deque(maxlen=stable_count)

    @property
    def offset_ms(self) -> float:
        return self._offset_ms

    def update(self, local_ms: float, exchange_ms: float) -> float:
        sample = local_ms - exchange_ms
        self._recent_diffs.append(sample)
        self._try_reset(sample)
        self._window.append(sample)
        self._offset_ms = statistics.median(self._window)
        return self._offset_ms

    def _try_reset(self, current_sample: float):
        """If last N samples are stable, discard old entries that deviate >2s."""
        if len(self._recent_diffs) < self._stable_count:
            return
        recent = list(self._recent_diffs)
        spread = max(recent) - min(recent)
        # "Stable" = recent N samples within 500ms of each other
        if spread > 500.0:
            return
        median_recent = statistics.median(recent)
        new_window: deque[float] = deque(maxlen=self._window_size)
        for val in self._window:
            if abs(val - median_recent) <= self._stale_discard_ms:
                new_window.append(val)
        if len(new_window) > 0:
            self._window = new_window

    def reset(self):
        """Full reset on reconnect."""
        self._window.clear()
        self._recent_diffs.clear()
        self._offset_ms = 0.0


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


class ExchangeSymbolSlot:
    """Per-exchange-per-symbol slot with its own lock."""

    def __init__(self, stale_threshold_ms: float, clock_window_size: int,
                 clock_stable_count: int, clock_stale_discard_ms: float):
        self.lock = asyncio.Lock()
        self.price: ExchangePrice | None = None
        self.clock = SlidingWindowClockEstimator(
            window_size=clock_window_size,
            stable_count=clock_stable_count,
            stale_discard_ms=clock_stale_discard_ms,
        )
        self._stale_threshold_ms = stale_threshold_ms

    async def update(self, exchange: str, symbol: str, best_bid: Decimal,
                     best_ask: Decimal, exchange_ts: int) -> None:
        async with self.lock:
            now_ms = time.time() * 1000
            offset = self.clock.update(now_ms, float(exchange_ts))
            self.price = ExchangePrice(
                exchange=exchange,
                symbol=symbol,
                best_bid=best_bid,
                best_ask=best_ask,
                exchange_timestamp=exchange_ts,
                local_receive_time=time.time(),
                clock_offset_ms=offset,
                is_stale=False,
            )

    async def get_price_if_valid(self) -> ExchangePrice | None:
        async with self.lock:
            if self.price is None or self.price.is_stale:
                return None
            now_ms = time.time() * 1000
            age_since_receive = (now_ms / 1000.0 - self.price.local_receive_time) * 1000.0
            if age_since_receive > self._stale_threshold_ms:
                self.price.is_stale = True
                return None
            adjusted_age = now_ms - (self.price.exchange_timestamp + self.price.clock_offset_ms)
            if adjusted_age > self._stale_threshold_ms:
                self.price.is_stale = True
                return None
            return self.price

    async def is_stale(self) -> bool:
        async with self.lock:
            if self.price is None:
                return False
            if self.price.is_stale:
                return True
            now_ms = time.time() * 1000
            age_since_receive = (now_ms / 1000.0 - self.price.local_receive_time) * 1000.0
            if age_since_receive > self._stale_threshold_ms:
                return True
            adjusted_age = now_ms - (self.price.exchange_timestamp + self.price.clock_offset_ms)
            return adjusted_age > self._stale_threshold_ms

    async def mark_stale(self) -> None:
        async with self.lock:
            if self.price:
                self.price.is_stale = True

    async def clear_stale(self) -> None:
        """Clear stale flag (on reconnect). Keeps existing price until fresh data arrives."""
        async with self.lock:
            if self.price:
                self.price.is_stale = False
                self.price.local_receive_time = time.time()
            self.clock.reset()


class PriceTable:
    """Per-exchange-per-symbol lock sharding. Each (exchange, symbol) pair has its own lock."""

    def __init__(self, stale_threshold_ms: float = 5000.0, clock_window_size: int = 20,
                 clock_stable_count: int = 5, clock_stale_discard_ms: float = 2000.0):
        self._slots: dict[str, ExchangeSymbolSlot] = {}
        self._stale_threshold_ms = stale_threshold_ms
        self._clock_window_size = clock_window_size
        self._clock_stable_count = clock_stable_count
        self._clock_stale_discard_ms = clock_stale_discard_ms
        self._known_exchanges: set[str] = set()
        self._known_symbols: set[str] = set()

    def _slot_key(self, exchange: str, symbol: str) -> str:
        return f"{exchange}:{symbol}"

    def _get_slot(self, exchange: str, symbol: str) -> ExchangeSymbolSlot:
        key = self._slot_key(exchange, symbol)
        if key not in self._slots:
            self._slots[key] = ExchangeSymbolSlot(
                stale_threshold_ms=self._stale_threshold_ms,
                clock_window_size=self._clock_window_size,
                clock_stable_count=self._clock_stable_count,
                clock_stale_discard_ms=self._clock_stale_discard_ms,
            )
            self._known_exchanges.add(exchange)
            self._known_symbols.add(symbol)
        return self._slots[key]

    async def update(self, exchange: str, symbol: str, best_bid: Decimal,
                     best_ask: Decimal, exchange_ts: int) -> None:
        slot = self._get_slot(exchange, symbol)
        await slot.update(exchange, symbol, best_bid, best_ask, exchange_ts)

    async def get_valid_prices(self, symbol: str = "BTC/USDT") -> dict[str, ExchangePrice]:
        valid = {}
        for exchange in list(self._known_exchanges):
            key = self._slot_key(exchange, symbol)
            slot = self._slots.get(key)
            if slot is None:
                continue
            price = await slot.get_price_if_valid()
            if price:
                valid[exchange] = price
        return valid

    async def get_stale_exchanges(self, symbol: str = "BTC/USDT") -> list[str]:
        stale = []
        for exchange in list(self._known_exchanges):
            key = self._slot_key(exchange, symbol)
            slot = self._slots.get(key)
            if slot is None:
                continue
            if await slot.is_stale():
                stale.append(exchange)
        return stale

    async def mark_exchange_stale(self, exchange: str, symbol: str | None = None) -> None:
        """Mark exchange stale for one symbol or all symbols."""
        if symbol:
            slot = self._slots.get(self._slot_key(exchange, symbol))
            if slot:
                await slot.mark_stale()
        else:
            for sym in list(self._known_symbols):
                slot = self._slots.get(self._slot_key(exchange, sym))
                if slot:
                    await slot.mark_stale()

    async def clear_exchange_stale(self, exchange: str) -> None:
        """On reconnect: clear stale for all symbols of this exchange."""
        for sym in list(self._known_symbols):
            slot = self._slots.get(self._slot_key(exchange, sym))
            if slot:
                await slot.clear_stale()

    async def get_all_prices(self, symbol: str = "BTC/USDT") -> dict[str, ExchangePrice]:
        result = {}
        for exchange in list(self._known_exchanges):
            key = self._slot_key(exchange, symbol)
            slot = self._slots.get(key)
            if slot:
                async with slot.lock:
                    if slot.price:
                        result[exchange] = slot.price
        return result
