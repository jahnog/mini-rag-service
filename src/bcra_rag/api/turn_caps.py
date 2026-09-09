from __future__ import annotations

import time
from collections.abc import Callable
from datetime import UTC, datetime


class TurnCaps:
    def __init__(
        self,
        *,
        max_email: int,
        max_process: int,
        time_fn: Callable[[], float] = time.time,
    ) -> None:
        self._max_email = max_email
        self._max_process = max_process
        self.time_fn = time_fn
        self._email_day: dict[tuple[str, str], int] = {}
        self._process_day: dict[str, int] = {}

    def allow(self, email: str) -> str | None:
        now = self.time_fn()
        day = datetime.fromtimestamp(now, tz=UTC).strftime("%Y-%m-%d")
        email_key = (email, day)
        used_email = self._email_day.get(email_key, 0)
        if used_email >= self._max_email:
            return "email_cap"
        used_process = self._process_day.get(day, 0)
        if used_process >= self._max_process:
            return "process_cap"
        self._email_day[email_key] = used_email + 1
        self._process_day[day] = used_process + 1
        return None
