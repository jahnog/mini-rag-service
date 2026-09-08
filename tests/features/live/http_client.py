"""Live HTTP helper against LIVE_BASE_URL. Origin/Referer must match AUTH_PUBLIC_ORIGIN."""

from __future__ import annotations

import os
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

import httpx

from bcra_rag.auth.origin import origin_matches
from tests.conftest import DEFAULT_LIVE_BASE_URL
from tests.features.live.mailbox import (
    DEFAULT_OTP_TTL_S,
    ImapSettings,
    Mailbox,
    MailboxTimeout,
    OtpMail,
    consume_used,
    find_leftover_otp,
    wait_for_new_otp,
)

CHAT_TIMEOUT_S = 120.0


class LiveHttpError(RuntimeError):
    """Misconfigured live HTTP client or unexpected status."""


class ProcessLimiterError(LiveHttpError):
    """HTTP 429 from the process 20/60s limiter — fail-fast, do not skip."""


@dataclass(frozen=True)
class LiveAuthResult:
    mail: OtpMail
    set_cookie: str
    sent_new: bool


def load_live_dotenv(path: Path | None = None) -> None:
    env_path = path or Path(".env")
    if not env_path.is_file():
        return
    for raw in env_path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip("'").strip('"')
        if key and key not in os.environ:
            os.environ[key] = value


def live_base_url() -> str:
    load_live_dotenv()
    return os.environ.get("LIVE_BASE_URL", DEFAULT_LIVE_BASE_URL).rstrip("/")


def public_origin() -> str:
    load_live_dotenv()
    return os.environ.get("AUTH_PUBLIC_ORIGIN", "").strip()


def cookie_name() -> str:
    load_live_dotenv()
    return os.environ.get("AUTH_COOKIE_NAME", "session").strip() or "session"


def require_origin_match(base_url: str, public: str) -> None:
    if not public or not origin_matches(public, base_url):
        raise LiveHttpError(
            f"LIVE_BASE_URL {base_url} does not origin-match AUTH_PUBLIC_ORIGIN {public}"
        )


def require_imap_env() -> ImapSettings:
    load_live_dotenv()
    return ImapSettings.from_env()


def browser_headers(base_url: str) -> dict[str, str]:
    origin = base_url.rstrip("/")
    headers = {"Origin": origin, "Referer": f"{origin}/"}
    demo = os.environ.get("DEMO_API_KEY", "").strip()
    if demo:
        headers["x-demo-key"] = demo
    return headers


def raise_for_limiter(response: httpx.Response, *, what: str) -> None:
    if response.status_code == 429:
        raise ProcessLimiterError(
            f"HTTP 429 from the process limiter during {what}; "
            "restart the process or wait"
        )


def make_client(base_url: str | None = None) -> httpx.Client:
    base = (base_url or live_base_url()).rstrip("/")
    require_origin_match(base, public_origin())
    return httpx.Client(
        base_url=base,
        headers=browser_headers(base),
        timeout=httpx.Timeout(CHAT_TIMEOUT_S),
        follow_redirects=True,
    )


def clone_client(client: httpx.Client) -> httpx.Client:
    cloned = make_client(str(client.base_url).rstrip("/"))
    for name, value in client.cookies.items():
        cloned.cookies.set(name, value)
    return cloned


def post_chat(client: httpx.Client, message: str) -> httpx.Response:
    response = client.post("/chat", json={"message": message})
    raise_for_limiter(response, what="POST /chat")
    return response


def post_chat_clear(
    client: httpx.Client, session_id: str | None = None
) -> httpx.Response:
    payload = {"session_id": session_id or str(uuid.uuid4())}
    response = client.post("/chat/clear", json=payload)
    raise_for_limiter(response, what="POST /chat/clear")
    return response


def authenticate_from_mailbox(
    client: httpx.Client,
    mailbox: Mailbox,
    email: str,
    *,
    new_timeout_s: float = 30.0,
    leftover_ttl_s: float = DEFAULT_OTP_TTL_S,
    now_fn: Callable[[], datetime] = lambda: datetime.now(UTC),
) -> LiveAuthResult:
    started = now_fn()
    requested = client.post("/auth/request", json={"email": email})
    raise_for_limiter(requested, what="POST /auth/request")
    if requested.status_code != 200:
        raise LiveHttpError(f"POST /auth/request returned {requested.status_code}")
    sent_new = True
    try:
        mail = wait_for_new_otp(mailbox, since=started, timeout_s=new_timeout_s)
    except MailboxTimeout:
        leftover = find_leftover_otp(mailbox, now=now_fn(), ttl_s=leftover_ttl_s)
        if leftover is None:
            raise LiveHttpError(
                "no new OTP mail and no leftover UNSEEN secret within OTP TTL"
            ) from None
        mail = leftover
        sent_new = False
    verified = client.post("/auth/verify", json={"email": email, "code": mail.code})
    raise_for_limiter(verified, what="POST /auth/verify")
    if verified.status_code != 200:
        raise LiveHttpError(f"POST /auth/verify returned {verified.status_code}")
    consume_used(mailbox, mail)
    return LiveAuthResult(
        mail=mail,
        set_cookie=verified.headers.get("set-cookie") or "",
        sent_new=sent_new,
    )
