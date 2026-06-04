import asyncio
import time
import random
import logging
from decimal import Decimal
from typing import AsyncIterator

from app.models.market import UnifiedOrderBook, UnifiedTrade, OrderBookLevel
from app.exchanges.base import BaseExchangeClient, MarketMessage

logger = logging.getLogger(__name__)


class MockClient(BaseExchangeClient):
    """Generates realistic fake BTC/USDT market data for testing."""

    def __init__(self, exchange_name: str = "mock", rate_ms: int = 50, base_price_offset: float = 0.0):
        super().__init__(exchange_name)
        self._rate_ms = rate_ms
        self._sequence = 0
        self._base_price = Decimal("67500.00") + Decimal(str(base_price_offset))
        self._trade_id = 1000000

    async def _send_subscriptions(self, ws) -> None:
        pass

    async def connect_and_stream(self) -> AsyncIterator[MarketMessage]:
        self._connected = True
        logger.info(f"Mock {self.name} WS started (subscriptions restored)")
        try:
            while True:
                self._sequence += 1
                yield self._generate_orderbook()
                if random.random() < 0.3:
                    self._trade_id += 1
                    yield self._generate_trade()
                await asyncio.sleep(self._rate_ms / 1000.0)
        finally:
            self._connected = False

    def _generate_orderbook(self) -> UnifiedOrderBook:
        spread = Decimal("0.50")
        mid = self._base_price + Decimal(str(random.uniform(-50, 50)))
        bids = []
        asks = []
        for i in range(20):
            offset = Decimal(str(i * 0.5 + random.uniform(0, 0.3)))
            bids.append(OrderBookLevel(
                price=mid - spread / 2 - offset,
                quantity=Decimal(str(round(random.uniform(0.01, 2.0), 4))),
            ))
            asks.append(OrderBookLevel(
                price=mid + spread / 2 + offset,
                quantity=Decimal(str(round(random.uniform(0.01, 2.0), 4))),
            ))
        return UnifiedOrderBook(
            msg_id=f"{self.name}:BTC/USDT:depth:{self._sequence}",
            exchange=self.name,
            symbol="BTC/USDT",
            timestamp=int(time.time() * 1000),
            sequence=self._sequence,
            bids=bids,
            asks=asks,
        )

    def _generate_trade(self) -> UnifiedTrade:
        mid = self._base_price + Decimal(str(random.uniform(-50, 50)))
        return UnifiedTrade(
            msg_id=f"{self.name}:BTC/USDT:trade:{self._trade_id}",
            exchange=self.name,
            symbol="BTC/USDT",
            trade_id=str(self._trade_id),
            price=mid,
            quantity=Decimal(str(round(random.uniform(0.001, 0.5), 4))),
            side=random.choice(["buy", "sell"]),
            timestamp=int(time.time() * 1000),
        )

    def parse_depth(self, raw: dict) -> UnifiedOrderBook:
        raise NotImplementedError

    def parse_trade(self, raw: dict) -> UnifiedTrade:
        raise NotImplementedError
