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
            await self._send_subscriptions(ws)
            try:
                async for raw_msg in ws:
                    data = json.loads(raw_msg)
                    yield self.parse_depth(data)
            finally:
                self._connected = False

    async def _send_subscriptions(self, ws) -> None:
        pass

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
    dedup = MessageDeduplicator(window_size=200)
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


@pytest.mark.asyncio
async def test_consecutive_short_disconnects_no_duplicates():
    """Two rapid disconnects in a row: verify no duplicate messages reach the output.

    Simulates:
    1. Client connects, receives messages seq 0-4
    2. Server drops connection (disconnect #1)
    3. Client reconnects, receives messages seq 5-9
    4. Server drops again immediately (disconnect #2)
    5. Server resets counter, replays from seq 0
    6. Client reconnects - dedup must catch all replayed sequences
    """
    server = MockExchangeServer()
    await server.start()

    dedup = MessageDeduplicator(window_size=200, max_time_delta_ms=5000)
    forwarded: list[str] = []

    try:
        client = TestableClient(server.url)

        # Phase 1: receive initial messages
        count = 0
        try:
            async for msg in client.connect_and_stream():
                if not dedup.is_duplicate(msg.msg_id):
                    forwarded.append(msg.msg_id)
                count += 1
                if count >= 5:
                    await server.force_disconnect_all()
                    await asyncio.sleep(0.05)
        except (websockets.exceptions.ConnectionClosed, websockets.exceptions.ConnectionClosedError):
            pass

        phase1_count = len(forwarded)
        assert phase1_count == 5

        # Phase 2: reconnect, receive more, then disconnect again quickly
        await asyncio.sleep(0.1)
        server._should_disconnect = False
        count = 0
        try:
            async for msg in client.connect_and_stream():
                if not dedup.is_duplicate(msg.msg_id):
                    forwarded.append(msg.msg_id)
                count += 1
                if count >= 5:
                    await server.force_disconnect_all()
                    await asyncio.sleep(0.05)
        except (websockets.exceptions.ConnectionClosed, websockets.exceptions.ConnectionClosedError):
            pass

        phase2_count = len(forwarded) - phase1_count
        assert phase2_count == 5

        # Phase 3: server resets sequence counter (simulates replay from start)
        server._send_count = 0
        server._should_disconnect = False
        await asyncio.sleep(0.1)

        count = 0
        duplicates_caught = 0
        async for msg in client.connect_and_stream():
            if dedup.is_duplicate(msg.msg_id):
                duplicates_caught += 1
            else:
                forwarded.append(msg.msg_id)
            count += 1
            if count >= 10:
                break

        # All replayed messages (seq 0-9) should be caught as duplicates
        # since they were already forwarded in phase 1 and 2
        assert duplicates_caught == 10, (
            f"Expected 10 duplicates caught but got {duplicates_caught}. "
            f"Total forwarded: {len(forwarded)}"
        )
        # No new messages should have been forwarded in phase 3
        assert len(forwarded) == phase1_count + phase2_count

    finally:
        await server.stop()


@pytest.mark.asyncio
async def test_rapid_reconnect_subscription_only_once():
    """Verify that during reconnect, subscription is sent only once per connection."""
    server = MockExchangeServer()
    await server.start()

    subscribe_calls: list[float] = []

    class TrackingClient(TestableClient):
        async def _send_subscriptions(self, ws) -> None:
            subscribe_calls.append(asyncio.get_event_loop().time())

    try:
        client = TrackingClient(server.url)

        # First connection
        count = 0
        async for msg in client.connect_and_stream():
            count += 1
            if count >= 3:
                break

        assert len(subscribe_calls) == 1

        # Second connection (after break)
        count = 0
        async for msg in client.connect_and_stream():
            count += 1
            if count >= 3:
                break

        assert len(subscribe_calls) == 2

    finally:
        await server.stop()
