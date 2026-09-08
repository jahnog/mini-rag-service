from __future__ import annotations

from typing import Any
from urllib.parse import urlparse

from bcra_rag.auth.settings import AuthSettings


def origin_matches(expected: str, incoming: str) -> bool:
    want_raw = (expected or "").strip()
    got_raw = (incoming or "").strip()
    if not want_raw:
        return True
    if not got_raw:
        return False
    want = urlparse(want_raw)
    got = urlparse(got_raw)
    if (want.scheme or "").lower() != (got.scheme or "").lower():
        return False
    if (want.hostname or "").lower() != (got.hostname or "").lower():
        return False
    return _port(want) == _port(got)


def cookie_secure(request: Any, settings: AuthSettings) -> bool:
    public = settings.public_origin.strip()
    if _scheme(public) == "https":
        return True
    if settings.trust_proxy:
        proto = (_header(request, "x-forwarded-proto") or "").split(",")[0].strip()
        if proto.lower() == "https":
            return True
    incoming = _header(request, "origin") or _header(request, "referer") or ""
    if _scheme(incoming) == "https":
        return True
    url = getattr(request, "url", None)
    return str(getattr(url, "scheme", "") or "").lower() == "https"


def _scheme(value: str) -> str:
    if not value:
        return ""
    return (urlparse(value).scheme or "").lower()


def _port(parsed: Any) -> int | None:
    port = getattr(parsed, "port", None)
    if port is not None:
        return int(port)
    scheme = (getattr(parsed, "scheme", None) or "").lower()
    if scheme == "https":
        return 443
    if scheme == "http":
        return 80
    return None


def _header(request: Any, name: str) -> str | None:
    headers = getattr(request, "headers", None)
    if headers is None:
        return None
    getter = getattr(headers, "get", None)
    if callable(getter):
        value = getter(name) or getter(name.title()) or getter(name.upper())
        return str(value) if value else None
    return None
