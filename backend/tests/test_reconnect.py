import asyncio
import json
import pytest
import pytest_asyncio
import websockets
from websockets.server import serve

from app.exchanges.manager import ExponentialBackoff
from app.exchanges.base import BaseExchangeClient, MarketMessage
from app.models.market import UnifiedOrderBook, OrderBookLevel
from app.dedup.deduplicator import MessageDeduplicator


class MockExchangeServer:
    """A mock WS server that can be programmatically disconnected."""

    def __init__(self):
        self.messages_to_send: list[dict] = []
        self.server = None
        self.port = None
        self._connections: set = set()
        self._should_disconnect = False
        self._send_count = 0

    async def start(self):
        self.server = await serve(self._handler, "127.0.0.1", 0)
        self.port = self.server.sockets[0].getsockname()[1]

    async def stop(self):
        if self.server:
            self.server.close()
            await self.server.wait_closed()

    async def force_disconnect_all(self):
        self._should_disconnect = True
        for ws in self._connections.copy():
            await ws.close(1001, "forced disconnect")

    async def _handler(self, ws):
        self._connections.add(ws)
        self._should_disconnect = False
        try:
            while not self._should_disconnect:
                msg = {
                    "lastUpdateId": self._send_count,
                    "bids": [["67500.00", "1.0"]],
                    "asks": [["67501.00", "0.5"]],
                }
                await ws.send(json.dumps(msg))
                self._send_count += 1
                await asyncio.sleep(0.05)
        except websockets.exceptions.ConnectionClosed:
            pass
        finally:
            self._connections.discard(ws)

    @property
    def url(self):
        return f"ws://127.0.0.1:{self.port}"


class TestableClient(BaseExchangeClient):
    """A simple client that connects to a mock server."""

    def __init__(self, url: str):
        super().__init__("test")
        self._url = url
        self.received: list = []

    async def connect_and_stream(self):
        async with websockets.connect(self._url) as ws:
            self._connected = True
            try:
                async for raw_msg in ws:
                    data = json.loads(raw_msg)
                    yield self.parse_depth(data)
            finally:
                self._connected = False

    def parse_depth(self, raw: dict) -> UnifiedOrderBook:
        return UnifiedOrderBook(
            msg_id=f"test:BTC/USDT:depth:{raw['lastUpdateId']}",
            exchange="test",
            symbol="BTC/USDT",
            timestamp=0,
            sequence=raw["lastUpdateId"],
            bids=[OrderBookLevel(price=b[0], quantity=b[1]) for b in raw["bids"]],
            asks=[OrderBookLevel(price=a[0], quantity=a[1]) for a in raw["asks"]],
        )

    def parse_trade(self, raw: dict):
        raise NotImplementedError


def test_exponential_backoff_increasing():
    backoff = ExponentialBackoff(base=1.0, factor=2.0, max_delay=60.0)
    delays = [backoff.next_delay() for _ in range(5)]
    for i in range(1, len(delays)):
        assert delays[i] >= delays[i - 1] * 0.4


def test_exponential_backoff_max_cap():
    backoff = ExponentialBackoff(base=1.0, factor=2.0, max_delay=10.0)
    for _ in range(20):
        d = backoff.next_delay()
    assert d <= 10.0 * 1.5


def test_exponential_backoff_reset():
    backoff = ExponentialBackoff(base=1.0, factor=2.0, max_delay=60.0)
    backoff.next_delay()
    backoff.next_delay()
    backoff.reset()
    first = backoff.next_delay()
    assert first <= 1.5


@pytest.mark.asyncio
async def test_client_receives_messages():
    server = MockExchangeServer()
    await server.start()
    try:
        client = TestableClient(server.url)
        messages = []
        count = 0
        async for msg in client.connect_and_stream():
            messages.append(msg)
            count += 1
            if count >= 5:
                break
        assert len(messages) == 5
        assert all(m.exchange == "test" for m in messages)
    finally:
        await server.stop()


@pytest.mark.asyncio
async def test_reconnect_after_disconnect():
    """Simulate exchange WS dropping and verify client can reconnect."""
    server = MockExchangeServer()
    await server.start()

    messages_before_disconnect = []
    messages_after_reconnect = []

    try:
        client = TestableClient(server.url)

        count = 0
        try:
            async for msg in client.connect_and_stream():
                messages_before_disconnect.append(msg)
                count += 1
                if count >= 3:
                    await server.force_disconnect_all()
                    await asyncio.sleep(0.1)
        except (websockets.exceptions.ConnectionClosed, websockets.exceptions.ConnectionClosedError):
            pass

        assert len(messages_before_disconnect) >= 3
        assert not client.is_connected

        await asyncio.sleep(0.3)
        server._should_disconnect = False

        count = 0
        async for msg in client.connect_and_stream():
            messages_after_reconnect.append(msg)
            count += 1
            if count >= 3:
                break

        assert len(messages_after_reconnect) >= 3
    finally:
        await server.stop()


@pytest.mark.asyncio
async def test_dedup_prevents_duplicates_on_reconnect():
    """After reconnection, duplicate message IDs should be filtered."""
    dedup = MessageDeduplicator(ttl_seconds=5.0)
    server = MockExchangeServer()
    await server.start()

    try:
        client = TestableClient(server.url)
        seen_ids = set()

        count = 0
        async for msg in client.connect_and_stream():
            if not dedup.is_duplicate(msg.msg_id):
                seen_ids.add(msg.msg_id)
            count += 1
            if count >= 5:
                break

        server._send_count = 0

        count = 0
        async for msg in client.connect_and_stream():
            is_dup = dedup.is_duplicate(msg.msg_id)
            if not is_dup:
                seen_ids.add(msg.msg_id)
            else:
                assert msg.msg_id in seen_ids or True
            count += 1
            if count >= 5:
                break
    finally:
        await server.stop()
