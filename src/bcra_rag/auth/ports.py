from __future__ import annotations

from typing import Protocol


class Mailer(Protocol):
    @property
    def configured(self) -> bool: ...

    def send_otp(
        self, *, to: str, code: str, login_url: str | None = None
    ) -> None: ...
