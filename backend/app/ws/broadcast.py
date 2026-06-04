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

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self._connections.add(websocket)
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
        dead: list[WebSocket] = []

        for ws in self._connections.copy():
            try:
                await ws.send_json(payload)
            except Exception:
                dead.append(ws)

        for ws in dead:
            self._connections.discard(ws)

    async def broadcast_raw(self, payload: dict):
        if not self._connections:
            return
        dead: list[WebSocket] = []
        for ws in self._connections.copy():
            try:
                await ws.send_json(payload)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self._connections.discard(ws)

    @property
    def client_count(self) -> int:
        return len(self._connections)


connection_manager = ConnectionManager()
