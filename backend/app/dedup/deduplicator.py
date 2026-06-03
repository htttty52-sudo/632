import time
from collections import OrderedDict


class MessageDeduplicator:
    def __init__(self, ttl_seconds: float = 5.0, max_size: int = 10000):
        self._seen: OrderedDict[str, float] = OrderedDict()
        self._ttl = ttl_seconds
        self._max_size = max_size

    def is_duplicate(self, msg_id: str) -> bool:
        now = time.monotonic()
        self._evict_expired(now)
        if msg_id in self._seen:
            return True
        self._seen[msg_id] = now
        if len(self._seen) > self._max_size:
            self._seen.popitem(last=False)
        return False

    def _evict_expired(self, now: float):
        while self._seen:
            oldest_key = next(iter(self._seen))
            if now - self._seen[oldest_key] > self._ttl:
                self._seen.popitem(last=False)
            else:
                break

    def clear(self):
        self._seen.clear()

    @property
    def size(self) -> int:
        return len(self._seen)
