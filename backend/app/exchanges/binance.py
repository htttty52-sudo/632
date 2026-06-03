import json
import time
import logging
from typing import AsyncIterator

import websockets

from app.config import settings
from app.models.market import UnifiedOrderBook, UnifiedTrade, OrderBookLevel
from app.exchanges.base import BaseExchangeClient, MarketMessage

logger = logging.getLogger(__name__)


class BinanceClient(BaseExchangeClient):
    def __init__(self):
        super().__init__("binance")
        symbol = settings.symbols[0].replace("/", "").lower()
        self._depth_url = f"{settings.binance_ws_url}/{symbol}@depth20@100ms"
        self._trade_url = f"{settings.binance_ws_url}/{symbol}@trade"

    async def connect_and_stream(self) -> AsyncIterator[MarketMessage]:
        symbol = settings.symbols[0].replace("/", "").lower()
        combined_url = f"{settings.binance_ws_url}/{symbol}@depth20@100ms/{symbol}@trade"

        async with websockets.connect(combined_url) as ws:
            self._connected = True
            logger.info("Binance WS connected")
            try:
                async for raw_msg in ws:
                    data = json.loads(raw_msg)
                    if "lastUpdateId" in data:
                        yield self.parse_depth(data)
                    elif "e" in data and data["e"] == "trade":
                        yield self.parse_trade(data)
            finally:
                self._connected = False

    def parse_depth(self, raw: dict) -> UnifiedOrderBook:
        return UnifiedOrderBook(
            msg_id=f"binance:BTC/USDT:depth:{raw['lastUpdateId']}",
            exchange="binance",
            symbol="BTC/USDT",
            timestamp=int(time.time() * 1000),
            sequence=raw["lastUpdateId"],
            bids=[OrderBookLevel(price=b[0], quantity=b[1]) for b in raw["bids"][:20]],
            asks=[OrderBookLevel(price=a[0], quantity=a[1]) for a in raw["asks"][:20]],
        )

    def parse_trade(self, raw: dict) -> UnifiedTrade:
        return UnifiedTrade(
            msg_id=f"binance:BTC/USDT:trade:{raw['t']}",
            exchange="binance",
            symbol="BTC/USDT",
            trade_id=str(raw["t"]),
            price=raw["p"],
            quantity=raw["q"],
            side="sell" if raw.get("m", False) else "buy",
            timestamp=raw["T"],
        )
