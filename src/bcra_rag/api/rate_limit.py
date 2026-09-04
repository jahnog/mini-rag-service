from __future__ import annotations

import time


class RateLimiter:
    def __init__(self, *, max_requests: int, window_s: int) -> None:
        self._max = max_requests
        self._window = window_s
        self._hits: dict[str, list[float]] = {}

    def allow(self, client_id: str) -> bool:
        now = time.time()
        bucket = [ts for ts in self._hits.get(client_id, []) if now - ts < self._window]
        if len(bucket) >= self._max:
            self._hits[client_id] = bucket
            return False
        bucket.append(now)
        self._hits[client_id] = bucket
        return True
