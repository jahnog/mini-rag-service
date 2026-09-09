from __future__ import annotations

from typing import Any


def client_ip(request: Any, *, trusted_proxy: bool) -> str:
    if trusted_proxy:
        forwarded = _header(request, "x-forwarded-for")
        if forwarded:
            return forwarded.split(",")[0].strip()
    client = getattr(request, "client", None)
    host = getattr(client, "host", None) if client is not None else None
    if host:
        return str(host)
    return "unknown"


def _header(request: Any, name: str) -> str | None:
    headers = getattr(request, "headers", None)
    if headers is None:
        return None
    getter = getattr(headers, "get", None)
    if callable(getter):
        value = getter(name) or getter(name.title()) or getter(name.upper())
        return str(value) if value else None
    return None
