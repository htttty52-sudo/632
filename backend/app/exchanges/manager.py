import asyncio
import random
import logging

from app.config import settings
from app.dedup.deduplicator import MessageDeduplicator
from app.exchanges.base import BaseExchangeClient
from app.models.market import UnifiedOrderBook
from app.ws.broadcast import connection_manager
from app.arbitrage.price_table import PriceTable
from app.influxdb.writer import influx_writer

logger = logging.getLogger(__name__)


class ExponentialBackoff:
    def __init__(self, base: float = 1.0, factor: float = 2.0, max_delay: float = 60.0):
        self._base = base
        self._factor = factor
        self._max_delay = max_delay
        self._attempt = 0

    def next_delay(self) -> float:
        delay = min(self._base * (self._factor ** self._attempt), self._max_delay)
        self._attempt += 1
        jitter = 0.5 + random.random()
        return delay * jitter

    def reset(self):
        self._attempt = 0


class ReconnectState:
    """Per-exchange reconnect state with lock to prevent duplicate subscriptions."""

    def __init__(self):
        self.lock = asyncio.Lock()
        self.reconnect_count = 0
        self.is_reconnecting = False


class ExchangeManager:
    def __init__(self):
        self._clients: dict[str, BaseExchangeClient] = {}
        self._tasks: dict[str, asyncio.Task] = {}
        self._states: dict[str, ReconnectState] = {}
        self._dedup = MessageDeduplicator(window_size=settings.dedup_max_size)
        self._running = False
        self.price_table = PriceTable(
            stale_threshold_ms=settings.stale_threshold_ms,
            clock_window_size=settings.clock_window_size,
            clock_stable_count=settings.clock_stable_count,
            clock_stale_discard_ms=settings.clock_stale_discard_ms,
        )

    async def start(self):
        self._running = True
        self._init_clients()
        for name, client in self._clients.items():
            self._states[name] = ReconnectState()
            self._tasks[name] = asyncio.create_task(self._run_with_reconnect(name, client))
        logger.info(f"ExchangeManager started with clients: {list(self._clients.keys())}")

    async def stop(self):
        self._running = False
        for task in self._tasks.values():
            task.cancel()
        await asyncio.gather(*self._tasks.values(), return_exceptions=True)
        self._tasks.clear()
        logger.info("ExchangeManager stopped")

    def _init_clients(self):
        if settings.use_mock:
            from app.exchanges.mock import MockClient
            self._clients["mock_binance"] = MockClient("mock_binance", rate_ms=50, base_price_offset=0.0)
            self._clients["mock_okx"] = MockClient("mock_okx", rate_ms=80, base_price_offset=15.0)
            self._clients["mock_huobi"] = MockClient("mock_huobi", rate_ms=70, base_price_offset=-10.0)
        else:
            from app.exchanges.binance import BinanceClient
            from app.exchanges.okx import OKXClient
            from app.exchanges.huobi import HuobiClient
            self._clients["binance"] = BinanceClient()
            self._clients["okx"] = OKXClient()
            self._clients["huobi"] = HuobiClient()

    async def _run_with_reconnect(self, name: str, client: BaseExchangeClient):
        backoff = ExponentialBackoff(
            base=settings.reconnect_base_delay,
            factor=settings.reconnect_factor,
            max_delay=settings.reconnect_max_delay,
        )
        state = self._states[name]
        delay = 0.0

        while self._running:
            async with state.lock:
                state.is_reconnecting = True
                try:
                    if state.reconnect_count > 0:
                        logger.info(
                            f"{name} reconnect #{state.reconnect_count}, "
                            "re-subscribing (lock held, single subscription guaranteed)"
                        )
                        # Clear stale for all symbols on reconnect
                        await self.price_table.clear_exchange_stale(name)
                    state.is_reconnecting = False

                    first_orderbook = True
                    async for msg in client.connect_and_stream():
                        if not self._running:
                            break
                        if not self._dedup.is_duplicate(msg.msg_id):
                            await connection_manager.broadcast(msg)
                            if isinstance(msg, UnifiedOrderBook) and msg.bids and msg.asks:
                                bid_depth = [(l.price, l.quantity) for l in msg.bids[:5]]
                                ask_depth = [(l.price, l.quantity) for l in msg.asks[:5]]
                                await self.price_table.update(
                                    exchange=msg.exchange,
                                    symbol=msg.symbol,
                                    best_bid=msg.bids[0].price,
                                    best_ask=msg.asks[0].price,
                                    exchange_ts=msg.timestamp,
                                    bid_depth=bid_depth,
                                    ask_depth=ask_depth,
                                )
                                influx_writer.record_orderbook(
                                    exchange=msg.exchange,
                                    symbol=msg.symbol,
                                    best_bid=msg.bids[0].price,
                                    best_ask=msg.asks[0].price,
                                    bid_depth=[(l.price, l.quantity) for l in msg.bids[:5]],
                                    ask_depth=[(l.price, l.quantity) for l in msg.asks[:5]],
                                    timestamp_ms=msg.timestamp,
                                )
                                if first_orderbook and state.reconnect_count > 0:
                                    first_orderbook = False
                                    logger.info(f"{name} reconnect price restored")
                    backoff.reset()
                except asyncio.CancelledError:
                    return
                except Exception as e:
                    if not self._running:
                        return
                    # Mark all symbols stale for this exchange
                    await self.price_table.mark_exchange_stale(name)
                    state.reconnect_count += 1
                    state.is_reconnecting = False
                    delay = backoff.next_delay()
                    logger.warning(f"{name} disconnected ({e}), reconnecting in {delay:.1f}s")

            if self._running and delay > 0:
                await asyncio.sleep(delay)
                delay = 0.0


exchange_manager = ExchangeManager()
