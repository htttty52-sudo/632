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
        self._symbol = symbol
        self._base_url = settings.binance_ws_url
        self._subscriptions = [
            f"{symbol}@depth20@100ms",
            f"{symbol}@trade",
        ]

    async def connect_and_stream(self) -> AsyncIterator[MarketMessage]:
        url = f"{self._base_url}/stream"
        async with websockets.connect(url) as ws:
            self._connected = True
            logger.info("Binance WS connected, sending subscriptions")
            await self._send_subscriptions(ws)
            try:
                async for raw_msg in ws:
                    data = json.loads(raw_msg)
                    if "result" in data:
                        continue
                    stream_data = data.get("data", data)
                    if "lastUpdateId" in stream_data:
                        yield self.parse_depth(stream_data)
                    elif stream_data.get("e") == "trade":
                        yield self.parse_trade(stream_data)
            finally:
                self._connected = False

    async def _send_subscriptions(self, ws) -> None:
        subscribe_msg = json.dumps({
            "method": "SUBSCRIBE",
            "params": self._subscriptions,
            "id": 1,
        })
        await ws.send(subscribe_msg)
        logger.info(f"Binance subscribed to: {self._subscriptions}")

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
