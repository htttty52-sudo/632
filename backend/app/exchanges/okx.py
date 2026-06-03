import json
import time
import logging
from typing import AsyncIterator

import websockets

from app.config import settings
from app.models.market import UnifiedOrderBook, UnifiedTrade, OrderBookLevel
from app.exchanges.base import BaseExchangeClient, MarketMessage

logger = logging.getLogger(__name__)


class OKXClient(BaseExchangeClient):
    def __init__(self):
        super().__init__("okx")
        self._url = settings.okx_ws_url

    async def connect_and_stream(self) -> AsyncIterator[MarketMessage]:
        async with websockets.connect(self._url) as ws:
            self._connected = True
            logger.info("OKX WS connected")

            subscribe_msg = json.dumps({
                "op": "subscribe",
                "args": [
                    {"channel": "books5", "instId": "BTC-USDT"},
                    {"channel": "trades", "instId": "BTC-USDT"},
                ]
            })
            await ws.send(subscribe_msg)

            try:
                async for raw_msg in ws:
                    data = json.loads(raw_msg)
                    if "event" in data:
                        continue
                    arg = data.get("arg", {})
                    channel = arg.get("channel", "")
                    if channel == "books5" and "data" in data:
                        yield self.parse_depth(data)
                    elif channel == "trades" and "data" in data:
                        for trade_data in data["data"]:
                            yield self.parse_trade(trade_data)
            finally:
                self._connected = False

    def parse_depth(self, raw: dict) -> UnifiedOrderBook:
        book = raw["data"][0]
        seq_id = int(book.get("seqId", book.get("ts", 0)))
        return UnifiedOrderBook(
            msg_id=f"okx:BTC/USDT:depth:{seq_id}",
            exchange="okx",
            symbol="BTC/USDT",
            timestamp=int(book["ts"]),
            sequence=seq_id,
            bids=[OrderBookLevel(price=b[0], quantity=b[1]) for b in book["bids"]],
            asks=[OrderBookLevel(price=a[0], quantity=a[1]) for a in book["asks"]],
        )

    def parse_trade(self, raw: dict) -> UnifiedTrade:
        return UnifiedTrade(
            msg_id=f"okx:BTC/USDT:trade:{raw['tradeId']}",
            exchange="okx",
            symbol="BTC/USDT",
            trade_id=raw["tradeId"],
            price=raw["px"],
            quantity=raw["sz"],
            side=raw["side"],
            timestamp=int(raw["ts"]),
        )
