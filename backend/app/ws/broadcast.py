import asyncio
import json
import logging
from typing import Union

from fastapi import WebSocket

from app.models.market import (
    UnifiedOrderBook, UnifiedTrade, SpreadSnapshot, SpreadMatrix, SpreadAlertEvent
)

logger = logging.getLogger(__name__)

MarketData = Union[UnifiedOrderBook, UnifiedTrade, SpreadSnapshot, SpreadMatrix, SpreadAlertEvent]


class ConnectionManager:
    def __init__(self):
        self._connections: set[WebSocket] = set()
        self._peak_connections: int = 0

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self._connections.add(websocket)
        if len(self._connections) > self._peak_connections:
            self._peak_connections = len(self._connections)
        logger.info(f"Client connected, total: {len(self._connections)}")

    def disconnect(self, websocket: WebSocket):
        self._connections.discard(websocket)
        logger.info(f"Client disconnected, total: {len(self._connections)}")

    async def broadcast(self, data: MarketData):
        if not self._connections:
            return

        if isinstance(data, UnifiedOrderBook):
            msg_type = "orderbook"
        elif isinstance(data, UnifiedTrade):
            msg_type = "trade"
        elif isinstance(data, SpreadMatrix):
            msg_type = "spread_matrix"
        elif isinstance(data, SpreadAlertEvent):
            msg_type = "spread_alert"
        else:
            msg_type = "spread"

        payload = {"type": msg_type, "data": data.model_dump(mode="json")}
        text = json.dumps(payload)
        await self._send_to_all(text)

    async def broadcast_raw(self, payload: dict):
        if not self._connections:
            return
        text = json.dumps(payload)
        await self._send_to_all(text)

    async def _send_to_all(self, text: str):
        """Send pre-serialized text to all connections concurrently."""
        dead: list[WebSocket] = []

        async def _send(ws: WebSocket):
            try:
                await ws.send_text(text)
            except Exception:
                dead.append(ws)

        await asyncio.gather(*[_send(ws) for ws in self._connections.copy()])

        for ws in dead:
            self._connections.discard(ws)

    @property
    def client_count(self) -> int:
        return len(self._connections)

    @property
    def metrics(self) -> dict:
        return {
            "connections": len(self._connections),
            "peak_connections": self._peak_connections,
        }


connection_manager = ConnectionManager()
