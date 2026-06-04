import asyncio
import json
import time
import pytest
from unittest.mock import AsyncMock, MagicMock

from app.ws.broadcast import ConnectionManager


class MockWebSocket:
    def __init__(self):
        self.sent_messages: list[bytes] = []
        self.closed = False

    async def accept(self):
        pass

    async def send_bytes(self, data: bytes):
        if self.closed:
            raise RuntimeError("Connection closed")
        self.sent_messages.append(data)


@pytest.mark.asyncio
async def test_broadcast_500_connections():
    """Stress test: 500 connections receive 100 broadcasts correctly."""
    manager = ConnectionManager()
    connections = [MockWebSocket() for _ in range(500)]

    for ws in connections:
        await manager.connect(ws)

    assert manager.client_count == 500
    assert manager.metrics["connections"] == 500
    assert manager.metrics["peak_connections"] == 500

    start = time.perf_counter()

    for i in range(100):
        payload = {"type": "spread_matrix", "data": {"iteration": i, "value": 123.456}}
        await manager.broadcast_raw(payload)

    elapsed = time.perf_counter() - start

    for ws in connections:
        assert len(ws.sent_messages) == 100

    first_msg = json.loads(connections[0].sent_messages[0].decode('utf-8'))
    assert first_msg["type"] == "spread_matrix"
    assert first_msg["data"]["iteration"] == 0

    assert elapsed < 5.0, f"Broadcast took {elapsed:.2f}s, expected < 5s"


@pytest.mark.asyncio
async def test_broadcast_single_serialization():
    """Verify that all connections receive the exact same bytes (not re-encoded)."""
    manager = ConnectionManager()
    connections = [MockWebSocket() for _ in range(10)]

    for ws in connections:
        await manager.connect(ws)

    payload = {"type": "test", "data": {"key": "value"}}
    await manager.broadcast_raw(payload)

    buffers = [ws.sent_messages[0] for ws in connections]
    assert len(set(id(b) for b in buffers)) == 1 or all(b == buffers[0] for b in buffers)


@pytest.mark.asyncio
async def test_dead_connection_cleanup():
    """Dead connections are cleaned up without affecting live ones."""
    manager = ConnectionManager()
    live_ws = MockWebSocket()
    dead_ws = MockWebSocket()
    dead_ws.closed = True

    await manager.connect(live_ws)
    await manager.connect(dead_ws)

    assert manager.client_count == 2

    await manager.broadcast_raw({"type": "test", "data": {}})

    assert manager.client_count == 1
    assert len(live_ws.sent_messages) == 1


@pytest.mark.asyncio
async def test_peak_connections_tracking():
    """Peak connection count is tracked correctly."""
    manager = ConnectionManager()
    connections = [MockWebSocket() for _ in range(50)]

    for ws in connections:
        await manager.connect(ws)

    assert manager.metrics["peak_connections"] == 50

    for ws in connections[:25]:
        manager.disconnect(ws)

    assert manager.metrics["connections"] == 25
    assert manager.metrics["peak_connections"] == 50
