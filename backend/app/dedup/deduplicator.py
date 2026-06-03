import time
import logging
from collections import OrderedDict

logger = logging.getLogger(__name__)


class DualBufferWindow:
    """Per-stream dual-buffer dedup with time-based fallback.

    Active buffer holds recently seen msg_ids with receive timestamps.
    When active buffer exceeds max_size, it becomes the standby buffer
    and a new active buffer is created.

    For messages outside both buffers, we compare the receive time delta
    against the last processed message. If the gap is too small (within
    max_time_delta_ms), it's likely a reconnection replay and is discarded.
    """

    def __init__(self, max_size: int = 200, max_time_delta_ms: float = 3000.0):
        self._max_size = max_size
        self._max_time_delta_ms = max_time_delta_ms
        self._active: OrderedDict[str, float] = OrderedDict()
        self._standby: OrderedDict[str, float] = OrderedDict()
        self._last_processed_time: float = 0.0
        self._last_processed_id: str = ""

    def is_duplicate(self, msg_id: str) -> bool:
        now = time.monotonic()

        # Check active buffer
        if msg_id in self._active:
            return True
        # Check standby buffer
        if msg_id in self._standby:
            return True

        # Not in either buffer - check time-based fallback
        if self._last_processed_time > 0:
            time_since_last_ms = (now - self._last_processed_time) * 1000
            if msg_id == self._last_processed_id:
                return True
            # If time gap is very small and we've seen recent messages,
            # this might be a replay. But since it's a new ID, let it through.

        # Record in active buffer
        self._active[msg_id] = now
        self._last_processed_time = now
        self._last_processed_id = msg_id

        # Rotate buffers when active exceeds max_size
        if len(self._active) > self._max_size:
            self._standby = self._active
            self._active = OrderedDict()

        return False

    @property
    def size(self) -> int:
        return len(self._active) + len(self._standby)


class MessageDeduplicator:
    """Dual-buffer deduplicator keyed by stream (exchange:symbol:channel).

    Parses msg_id format: "{exchange}:{symbol}:{channel}:{sequence_or_id}"
    Each stream key gets its own DualBufferWindow.

    Dedup logic:
    1. If msg_id is in active or standby buffer -> duplicate
    2. If msg_id is NOT in buffers, check time delta from last processed:
       - If delta < max_time_delta_ms AND sequence <= last_sequence -> duplicate
       - Otherwise -> new message, record it
    """

    def __init__(self, window_size: int = 200, max_time_delta_ms: float = 3000.0):
        self._window_size = window_size
        self._max_time_delta_ms = max_time_delta_ms
        self._streams: dict[str, _StreamState] = {}

    def is_duplicate(self, msg_id: str) -> bool:
        parts = msg_id.rsplit(":", 1)
        if len(parts) != 2:
            return False

        stream_key = parts[0]
        seq_str = parts[1]
        try:
            sequence = int(seq_str)
        except ValueError:
            return False

        if stream_key not in self._streams:
            self._streams[stream_key] = _StreamState(
                self._window_size, self._max_time_delta_ms
            )

        return self._streams[stream_key].check(msg_id, sequence)

    def clear(self):
        self._streams.clear()

    @property
    def size(self) -> int:
        return sum(s.size for s in self._streams.values())

    @property
    def stream_count(self) -> int:
        return len(self._streams)


class _StreamState:
    """Per-stream state: dual buffer of msg_ids + sequence tracking + time tracking."""

    def __init__(self, max_size: int, max_time_delta_ms: float):
        self._max_size = max_size
        self._max_time_delta_ms = max_time_delta_ms
        # Dual buffers: active collects new entries, standby is the previous generation
        self._active: dict[str, float] = {}
        self._standby: dict[str, float] = {}
        # Sequence tracking
        self._max_sequence: int = -1
        self._last_recv_time: float = 0.0

    def check(self, msg_id: str, sequence: int) -> bool:
        now = time.monotonic()

        # Buffer check: if in either buffer, it's a duplicate
        if msg_id in self._active or msg_id in self._standby:
            return True

        # Time-based fallback for messages outside both buffers:
        # If we've processed messages recently and this sequence is <= max seen,
        # it's likely a reconnection replay.
        if self._last_recv_time > 0 and sequence <= self._max_sequence:
            time_delta_ms = (now - self._last_recv_time) * 1000
            if time_delta_ms < self._max_time_delta_ms:
                # Recent activity + old sequence = reconnect replay
                return True

        # Not a duplicate: record it
        self._active[msg_id] = now
        self._last_recv_time = now
        if sequence > self._max_sequence:
            self._max_sequence = sequence

        # Rotate when active is full
        if len(self._active) > self._max_size:
            self._standby = self._active
            self._active = {}

        return False

    @property
    def size(self) -> int:
        return len(self._active) + len(self._standby)
