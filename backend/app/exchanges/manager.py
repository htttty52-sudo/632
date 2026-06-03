import asyncio
import random
import logging
from typing import Optional

from app.config import settings
from app.dedup.deduplicator import MessageDeduplicator
from app.exchanges.base import BaseExchangeClient
from app.ws.broadcast import connection_manager

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


class ExchangeManager:
    def __init__(self):
        self._clients: dict[str, BaseExchangeClient] = {}
        self._tasks: dict[str, asyncio.Task] = {}
        self._dedup = MessageDeduplicator(window_size=settings.dedup_max_size)
        self._running = False

    async def start(self):
        self._running = True
        self._init_clients()
        for name, client in self._clients.items():
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
            self._clients["mock_binance"] = MockClient("mock_binance", rate_ms=50)
            self._clients["mock_okx"] = MockClient("mock_okx", rate_ms=80)
        else:
            from app.exchanges.binance import BinanceClient
            from app.exchanges.okx import OKXClient
            self._clients["binance"] = BinanceClient()
            self._clients["okx"] = OKXClient()

    async def _run_with_reconnect(self, name: str, client: BaseExchangeClient):
        backoff = ExponentialBackoff(
            base=settings.reconnect_base_delay,
            factor=settings.reconnect_factor,
            max_delay=settings.reconnect_max_delay,
        )
        reconnect_count = 0
        while self._running:
            try:
                if reconnect_count > 0:
                    logger.info(f"{name} reconnect #{reconnect_count}, subscriptions will be re-sent")
                async for msg in client.connect_and_stream():
                    if not self._running:
                        break
                    if not self._dedup.is_duplicate(msg.msg_id):
                        await connection_manager.broadcast(msg)
                backoff.reset()
            except asyncio.CancelledError:
                break
            except Exception as e:
                if not self._running:
                    break
                reconnect_count += 1
                delay = backoff.next_delay()
                logger.warning(f"{name} disconnected ({e}), reconnecting in {delay:.1f}s")
                await asyncio.sleep(delay)


exchange_manager = ExchangeManager()
