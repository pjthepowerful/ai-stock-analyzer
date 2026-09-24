"""
A tiny thread-safe TTL cache for per-ticker lookups. Each lookup is several
upstream round trips (Yahoo, Polygon, EDGAR, news), and people flip back to
tickers they just viewed — so a short cache makes that instant without
serving anything meaningfully stale.
"""
import threading
import time
from typing import Any, Callable, Hashable


class TTLCache:
    def __init__(self, ttl: float, max_items: int = 512):
        self.ttl = ttl
        self.max_items = max_items
        self._data: dict[Hashable, tuple[float, Any]] = {}
        self._lock = threading.Lock()

    def get_or_set(self, key: Hashable, build: Callable[[], Any]) -> Any:
        now = time.time()
        with self._lock:
            hit = self._data.get(key)
            if hit and now - hit[0] < self.ttl:
                return hit[1]
        value = build()  # outside the lock: builds can take seconds
        with self._lock:
            if len(self._data) >= self.max_items:
                # Drop the oldest entry; simple and good enough at this size.
                oldest = min(self._data, key=lambda k: self._data[k][0])
                self._data.pop(oldest, None)
            self._data[key] = (time.time(), value)
        return value
