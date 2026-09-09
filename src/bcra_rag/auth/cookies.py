from __future__ import annotations

import base64
import hashlib
import hmac
import secrets

from bcra_rag.auth.settings import SECRET_MIN_LEN

INTENT_COOKIE = "auth_intent"
LINK_COOKIE = "auth_link"
LINK_COOKIE_PATH = "/auth/link"


def sign_session(*, email: str, secret: str, ttl_s: int, now: float) -> str:
    exp = int(now) + ttl_s
    nonce = secrets.token_hex(8)
    payload = f"{email}|{exp}|{nonce}"
    digest = _digest(secret, payload)
    raw = f"{payload}|{digest}".encode()
    return base64.urlsafe_b64encode(raw).decode()


def read_session(*, value: str, secret: str, now: float) -> str | None:
    if len(secret) < SECRET_MIN_LEN or not value:
        return None
    try:
        raw = base64.urlsafe_b64decode(value.encode())
        payload, given = raw.decode().rsplit("|", 1)
    except (ValueError, UnicodeDecodeError):
        return None
    expected = _digest(secret, payload)
    if not hmac.compare_digest(expected, given):
        return None
    try:
        email, exp_s, _nonce = payload.split("|", 2)
    except ValueError:
        return None
    try:
        exp = int(exp_s)
    except ValueError:
        return None
    if now >= exp or not email:
        return None
    return email


def _digest(secret: str, payload: str) -> str:
    return hmac.new(secret.encode(), payload.encode(), hashlib.sha256).hexdigest()
