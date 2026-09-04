from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field


@dataclass
class _Session:
    messages: list[tuple[str, str]] = field(default_factory=list)
    updated: float = field(default_factory=time.time)


class InMemorySessionStore:
    def __init__(self, *, ttl_s: float = 3600, cap: int = 200) -> None:
        self._ttl_s = ttl_s
        self._cap = cap
        self._sessions: dict[str, _Session] = {}

    def mint(self) -> str:
        self.expire()
        self._evict_if_capped()
        session_id = str(uuid.uuid4())
        self._sessions[session_id] = _Session()
        return session_id

    def get(self, session_id: str) -> list[tuple[str, str]]:
        self.expire()
        session = self._sessions.get(session_id)
        if session is None:
            return []
        return list(session.messages)

    def append(self, session_id: str, role: str, content: str) -> None:
        self.expire()
        session = self._sessions.get(session_id)
        if session is None:
            session = _Session()
            self._sessions[session_id] = session
            self._evict_if_capped(keep=session_id)
        session.messages.append((role, content))
        session.messages = session.messages[-6:]
        session.updated = time.time()

    def expire(self) -> None:
        now = time.time()
        stale = [
            key
            for key, session in self._sessions.items()
            if now - session.updated >= self._ttl_s
        ]
        for key in stale:
            del self._sessions[key]

    def clear(self, session_id: str) -> None:
        self._sessions.pop(session_id, None)

    def _evict_if_capped(self, keep: str | None = None) -> None:
        while len(self._sessions) >= self._cap:
            candidates = [key for key in self._sessions if key != keep]
            if not candidates:
                break
            oldest = min(candidates, key=lambda key: self._sessions[key].updated)
            del self._sessions[oldest]
