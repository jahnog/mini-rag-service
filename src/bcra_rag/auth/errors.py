from __future__ import annotations


class AuthUnavailable(Exception):
    """Signing secret missing or too short."""


class AuthRejected(Exception):
    def __init__(
        self,
        status: int,
        detail: str,
        *,
        retry_after: int | None = None,
    ) -> None:
        super().__init__(detail)
        self.status = status
        self.detail = detail
        self.retry_after = retry_after
