import asyncio
import time
import statistics
from collections import deque
from dataclasses import dataclass
from decimal import Decimal


class SlidingWindowClockEstimator:
    """Per-exchange sliding window of recent (local - exchange) time diffs, using median."""

    def __init__(self, window_size: int = 20):
        self._window: deque[float] = deque(maxlen=window_size)
        self._offset_ms: float = 0.0

    @property
    def offset_ms(self) -> float:
        return self._offset_ms

    def update(self, local_ms: float, exchange_ms: float) -> float:
        sample = local_ms - exchange_ms
        self._window.append(sample)
        self._offset_ms = statistics.median(self._window)
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


class SymbolShard:
    """Per-symbol shard with its own lock, price entries, and clock estimators."""

    def __init__(self, stale_threshold_ms: float, clock_window_size: int):
        self.lock = asyncio.Lock()
        self.prices: dict[str, ExchangePrice] = {}
        self.clocks: dict[str, SlidingWindowClockEstimator] = {}
        self._stale_threshold_ms = stale_threshold_ms
        self._clock_window_size = clock_window_size

    async def update(self, exchange: str, symbol: str, best_bid: Decimal,
                     best_ask: Decimal, exchange_ts: int) -> None:
        async with self.lock:
            now_ms = time.time() * 1000
            if exchange not in self.clocks:
                self.clocks[exchange] = SlidingWindowClockEstimator(
                    window_size=self._clock_window_size
                )
            offset = self.clocks[exchange].update(now_ms, float(exchange_ts))
            self.prices[exchange] = ExchangePrice(
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
        async with self.lock:
            now_ms = time.time() * 1000
            valid = {}
            for name, price in self.prices.items():
                if price.is_stale:
                    continue
                age_since_receive = (now_ms / 1000.0 - price.local_receive_time) * 1000.0
                if age_since_receive > self._stale_threshold_ms:
                    price.is_stale = True
                    continue
                adjusted_age = now_ms - (price.exchange_timestamp + price.clock_offset_ms)
                if adjusted_age > self._stale_threshold_ms:
                    price.is_stale = True
                else:
                    valid[name] = price
            return valid

    async def get_stale_exchanges(self) -> list[str]:
        async with self.lock:
            now_ms = time.time() * 1000
            stale = []
            for name, price in self.prices.items():
                if price.is_stale:
                    stale.append(name)
                    continue
                age_since_receive = (now_ms / 1000.0 - price.local_receive_time) * 1000.0
                if age_since_receive > self._stale_threshold_ms:
                    stale.append(name)
                    continue
                adjusted_age = now_ms - (price.exchange_timestamp + price.clock_offset_ms)
                if adjusted_age > self._stale_threshold_ms:
                    stale.append(name)
            return stale

    async def mark_exchange_stale(self, exchange: str) -> None:
        async with self.lock:
            if exchange in self.prices:
                self.prices[exchange].is_stale = True


class PriceTable:
    """Sharded price table: one lock per trading pair, allowing parallel updates across symbols."""

    def __init__(self, stale_threshold_ms: float = 5000.0, clock_window_size: int = 20):
        self._shards: dict[str, SymbolShard] = {}
        self._stale_threshold_ms = stale_threshold_ms
        self._clock_window_size = clock_window_size

    def _get_shard(self, symbol: str) -> SymbolShard:
        if symbol not in self._shards:
            self._shards[symbol] = SymbolShard(
                stale_threshold_ms=self._stale_threshold_ms,
                clock_window_size=self._clock_window_size,
            )
        return self._shards[symbol]

    async def update(self, exchange: str, symbol: str, best_bid: Decimal,
                     best_ask: Decimal, exchange_ts: int) -> None:
        shard = self._get_shard(symbol)
        await shard.update(exchange, symbol, best_bid, best_ask, exchange_ts)

    async def get_valid_prices(self, symbol: str = "BTC/USDT") -> dict[str, ExchangePrice]:
        shard = self._get_shard(symbol)
        return await shard.get_valid_prices()

    async def get_stale_exchanges(self, symbol: str = "BTC/USDT") -> list[str]:
        shard = self._get_shard(symbol)
        return await shard.get_stale_exchanges()

    async def mark_exchange_stale(self, exchange: str, symbol: str = "BTC/USDT") -> None:
        shard = self._get_shard(symbol)
        await shard.mark_exchange_stale(exchange)

    async def get_all_prices(self, symbol: str = "BTC/USDT") -> dict[str, ExchangePrice]:
        shard = self._get_shard(symbol)
        async with shard.lock:
            return dict(shard.prices)
