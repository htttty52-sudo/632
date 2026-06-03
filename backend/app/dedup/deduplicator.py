import logging
from collections import defaultdict

logger = logging.getLogger(__name__)


class SequenceWindow:
    """Sliding window dedup for a single stream (exchange:symbol:channel).

    Tracks the max sequence seen and a window of recent sequences.
    A message is a duplicate if its sequence <= max_seen and is within
    the window, or if its sequence has already been processed.
    """

    def __init__(self, window_size: int = 200):
        self._window_size = window_size
        self._max_seq: int = -1
        self._seen: set[int] = set()

    def is_duplicate(self, sequence: int) -> bool:
        if sequence in self._seen:
            return True

        if sequence <= self._max_seq - self._window_size:
            return False

        self._seen.add(sequence)

        if sequence > self._max_seq:
            self._max_seq = sequence
            self._evict()

        return False

    def _evict(self):
        if len(self._seen) > self._window_size * 2:
            cutoff = self._max_seq - self._window_size
            self._seen = {s for s in self._seen if s > cutoff}

    @property
    def max_seq(self) -> int:
        return self._max_seq

    @property
    def size(self) -> int:
        return len(self._seen)


class MessageDeduplicator:
    """Per-stream sequence-number sliding window deduplicator.

    Parses msg_id format: "{exchange}:{symbol}:{channel}:{sequence}"
    For each unique (exchange, symbol, channel), maintains a SequenceWindow.
    """

    def __init__(self, window_size: int = 200):
        self._window_size = window_size
        self._streams: dict[str, SequenceWindow] = defaultdict(
            lambda: SequenceWindow(window_size)
        )

    def is_duplicate(self, msg_id: str) -> bool:
        parts = msg_id.rsplit(":", 1)
        if len(parts) != 2:
            return False

        stream_key = parts[0]
        try:
            sequence = int(parts[1])
        except ValueError:
            return False

        return self._streams[stream_key].is_duplicate(sequence)

    def clear(self):
        self._streams.clear()

    @property
    def size(self) -> int:
        return sum(w.size for w in self._streams.values())

    @property
    def stream_count(self) -> int:
        return len(self._streams)
