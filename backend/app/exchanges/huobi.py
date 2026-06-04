import gzip
import json
import time
import logging
from typing import AsyncIterator

import websockets

from app.config import settings
from app.models.market import UnifiedOrderBook, UnifiedTrade, OrderBookLevel
from app.exchanges.base import BaseExchangeClient, MarketMessage

logger = logging.getLogger(__name__)


class HuobiClient(BaseExchangeClient):
    def __init__(self):
        super().__init__("huobi")
        self._url = settings.huobi_ws_url
        symbol = settings.symbols[0].replace("/", "").lower()
        self._symbol = symbol
        self._subscriptions = [
            {"sub": f"market.{symbol}.depth.step0", "id": "depth1"},
            {"sub": f"market.{symbol}.trade.detail", "id": "trade1"},
        ]
        self._sequence = 0

    async def connect_and_stream(self) -> AsyncIterator[MarketMessage]:
        async with websockets.connect(self._url) as ws:
            self._connected = True
            logger.info("Huobi WS connected, sending subscriptions")
            await self._send_subscriptions(ws)
            try:
                async for raw_msg in ws:
                    if isinstance(raw_msg, bytes):
                        raw_msg = gzip.decompress(raw_msg).decode("utf-8")
                    data = json.loads(raw_msg)
                    if "ping" in data:
                        await ws.send(json.dumps({"pong": data["ping"]}))
                        continue
                    if "subbed" in data:
                        continue
                    ch = data.get("ch", "")
                    if "depth" in ch and "tick" in data:
                        yield self.parse_depth(data)
                    elif "trade" in ch and "tick" in data:
                        for trade in data["tick"]["data"]:
                            yield self.parse_trade(trade)
            finally:
                self._connected = False

    async def _send_subscriptions(self, ws) -> None:
        for sub in self._subscriptions:
            await ws.send(json.dumps(sub))
        logger.info(f"Huobi subscribed to: {self._subscriptions}")

    def parse_depth(self, raw: dict) -> UnifiedOrderBook:
        tick = raw["tick"]
        ts = raw.get("ts", int(time.time() * 1000))
        self._sequence += 1
        return UnifiedOrderBook(
            msg_id=f"huobi:BTC/USDT:depth:{self._sequence}",
            exchange="huobi",
            symbol="BTC/USDT",
            timestamp=ts,
            sequence=self._sequence,
            bids=[OrderBookLevel(price=b[0], quantity=b[1]) for b in tick["bids"][:20]],
            asks=[OrderBookLevel(price=a[0], quantity=a[1]) for a in tick["asks"][:20]],
        )

    def parse_trade(self, raw: dict) -> UnifiedTrade:
        trade_id = str(raw.get("tradeId", raw.get("id", 0)))
        return UnifiedTrade(
            msg_id=f"huobi:BTC/USDT:trade:{trade_id}",
            exchange="huobi",
            symbol="BTC/USDT",
            trade_id=trade_id,
            price=raw["price"],
            quantity=raw["amount"],
            side="buy" if raw["direction"] == "buy" else "sell",
            timestamp=raw["ts"],
        )
