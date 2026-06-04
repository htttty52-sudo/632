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


class SharedMessage:
    """Reference-counted message buffer. Encode once, share across all connections."""

    __slots__ = ('_data', '_refcount')

    def __init__(self, data: bytes):
        self._data = data
        self._refcount = 0

    def acquire(self, count: int = 1):
        self._refcount += count

    def release(self):
        self._refcount -= 1
        if self._refcount <= 0:
            self._data = b''

    @property
    def data(self) -> bytes:
        return self._data


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
        raw = json.dumps(payload).encode('utf-8')
        await self._send_to_all(raw)

    async def broadcast_raw(self, payload: dict):
        if not self._connections:
            return
        raw = json.dumps(payload).encode('utf-8')
        await self._send_to_all(raw)

    async def _send_to_all(self, data: bytes):
        """Send pre-encoded bytes to all connections concurrently (copy-on-write: single buffer shared)."""
        dead: list[WebSocket] = []
        msg = SharedMessage(data)
        msg.acquire(len(self._connections))

        async def _send(ws: WebSocket):
            try:
                await ws.send_bytes(msg.data)
            except Exception:
                dead.append(ws)
            finally:
                msg.release()

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
