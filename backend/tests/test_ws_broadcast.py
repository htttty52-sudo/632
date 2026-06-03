import asyncio
import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, MagicMock
from fastapi import WebSocket

from app.ws.broadcast import ConnectionManager
from app.models.market import UnifiedOrderBook, OrderBookLevel


@pytest.mark.asyncio
async def test_broadcast_to_multiple_clients():
    manager = ConnectionManager()

    ws1 = AsyncMock(spec=WebSocket)
    ws2 = AsyncMock(spec=WebSocket)

    manager._connections.add(ws1)
    manager._connections.add(ws2)

    msg = UnifiedOrderBook(
        msg_id="test:BTC/USDT:depth:1",
        exchange="test",
        symbol="BTC/USDT",
        timestamp=1700000000000,
        sequence=1,
        bids=[OrderBookLevel(price="67500", quantity="1.0")],
        asks=[OrderBookLevel(price="67501", quantity="0.5")],
    )

    await manager.broadcast(msg)

    ws1.send_json.assert_called_once()
    ws2.send_json.assert_called_once()
    payload = ws1.send_json.call_args[0][0]
    assert payload["type"] == "orderbook"
    assert payload["data"]["exchange"] == "test"


@pytest.mark.asyncio
async def test_dead_client_removed_on_broadcast():
    manager = ConnectionManager()

    ws_good = AsyncMock(spec=WebSocket)
    ws_dead = AsyncMock(spec=WebSocket)
    ws_dead.send_json.side_effect = RuntimeError("connection closed")

    manager._connections.add(ws_good)
    manager._connections.add(ws_dead)

    msg = UnifiedOrderBook(
        msg_id="test:BTC/USDT:depth:2",
        exchange="test",
        symbol="BTC/USDT",
        timestamp=1700000000000,
        sequence=2,
        bids=[OrderBookLevel(price="67500", quantity="1.0")],
        asks=[OrderBookLevel(price="67501", quantity="0.5")],
    )

    await manager.broadcast(msg)

    assert ws_dead not in manager._connections
    assert ws_good in manager._connections
    assert manager.client_count == 1


@pytest.mark.asyncio
async def test_no_clients_broadcast_succeeds():
    manager = ConnectionManager()
    msg = UnifiedOrderBook(
        msg_id="test:BTC/USDT:depth:3",
        exchange="test",
        symbol="BTC/USDT",
        timestamp=1700000000000,
        sequence=3,
        bids=[],
        asks=[],
    )
    await manager.broadcast(msg)
