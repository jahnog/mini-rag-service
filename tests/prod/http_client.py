"""HTTP helper against PROD_BASE_URL. Origin/Referer must match AUTH_PUBLIC_ORIGIN."""

from __future__ import annotations

import os
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from urllib.parse import urlparse

import httpx

from bcra_rag.auth.origin import origin_matches
from tests.features.live.http_client import (
    browser_headers,
    load_live_dotenv,
    public_origin,
    raise_for_limiter,
)
from tests.features.live.mailbox import (
    Mailbox,
    OtpMail,
    consume_used,
    live_email,
    parse_login_url,
    snapshot_otp_uids,
    wait_for_new_otp,
)

DEFAULT_NEW_MAIL_TIMEOUT_S = 180.0
# max_sends_per_email_minute uses a 60s window; slack avoids a 429 on send 2.
SEND_GAP_S = 65.0
# AUTH min_verify_interval_s is 2.0; replay faster than that is HTTP 429.
VERIFY_GAP_S = 2.5
CHAT_TIMEOUT_S = 480.0
CHAT_RETRY_STATUSES = frozenset({502, 503, 504})
CHAT_RETRY_ATTEMPTS = 3
CHAT_RETRY_GAP_S = 30.0


class ProdHttpError(RuntimeError):
    """Misconfigured production smoke client or unexpected status."""


@dataclass(frozen=True)
class ProdAuthResult:
    mail: OtpMail
    set_cookie: str


@dataclass(frozen=True)
class ProdLinkResult:
    set_cookie: str
    confirm_html: str


def prod_base_url() -> str:
    load_live_dotenv()
    value = (os.environ.get("PROD_BASE_URL") or "").strip().rstrip("/")
    if not value:
        raise ProdHttpError("PROD_BASE_URL is required")
    return value


def require_origin_match(base_url: str, public: str) -> None:
    if not public or not origin_matches(public, base_url):
        raise ProdHttpError(
            f"PROD_BASE_URL {base_url} does not origin-match AUTH_PUBLIC_ORIGIN {public}"
        )


def require_prod_ready() -> str:
    base = prod_base_url()
    require_origin_match(base, public_origin())
    url = f"{base}/health"
    try:
        response = httpx.get(url, timeout=2.0, headers=browser_headers(base))
        response.raise_for_status()
    except Exception as exc:
        raise ProdHttpError(
            f"PROD_BASE_URL unreachable: {base} (did not spawn uvicorn): {exc}"
        ) from exc
    return base


def make_client(base_url: str | None = None) -> httpx.Client:
    base = (base_url or prod_base_url()).rstrip("/")
    require_origin_match(base, public_origin())
    return httpx.Client(
        base_url=base,
        headers=browser_headers(base),
        timeout=httpx.Timeout(CHAT_TIMEOUT_S),
        follow_redirects=True,
    )


def require_chat_json(response: httpx.Response, *, what: str) -> httpx.Response:
    raise_for_limiter(response, what=what)
    snippet = response.text[:200].replace("\n", " ")
    if response.status_code != 200:
        raise ProdHttpError(f"{what} returned {response.status_code}: {snippet}")
    try:
        payload = response.json()
    except Exception as exc:
        raise ProdHttpError(f"{what} returned non-JSON: {snippet}") from exc
    if not isinstance(payload, dict):
        raise ProdHttpError(f"{what} returned JSON that is not an object")
    return response


def post_chat(
    client: httpx.Client,
    message: str,
    *,
    sleep: Callable[[float], None] = time.sleep,
    attempts: int = CHAT_RETRY_ATTEMPTS,
) -> httpx.Response:
    last: httpx.Response | None = None
    for attempt in range(max(1, attempts)):
        response = client.post("/chat", json={"message": message})
        raise_for_limiter(response, what="POST /chat")
        if response.status_code not in CHAT_RETRY_STATUSES:
            return require_chat_json(response, what="POST /chat")
        last = response
        if attempt + 1 < max(1, attempts):
            sleep(CHAT_RETRY_GAP_S)
    assert last is not None
    return require_chat_json(last, what="POST /chat")


def request_otp(client: httpx.Client, email: str) -> httpx.Response:
    response = client.post("/auth/request", json={"email": email})
    raise_for_limiter(response, what="POST /auth/request")
    if response.status_code != 200:
        raise ProdHttpError(f"POST /auth/request returned {response.status_code}")
    return response


def wait_new_otp_mail(
    mailbox: Mailbox,
    *,
    since: datetime,
    timeout_s: float = DEFAULT_NEW_MAIL_TIMEOUT_S,
    seen_uids: frozenset[str] | None = None,
) -> OtpMail:
    return wait_for_new_otp(
        mailbox, since=since, timeout_s=timeout_s, seen_uids=seen_uids
    )


def authenticate_new_from_mailbox(
    client: httpx.Client,
    mailbox: Mailbox,
    email: str,
    *,
    new_timeout_s: float = DEFAULT_NEW_MAIL_TIMEOUT_S,
    now_fn: Callable[[], datetime] = lambda: datetime.now(UTC),
) -> ProdAuthResult:
    seen = snapshot_otp_uids(mailbox)
    started = now_fn()
    request_otp(client, email)
    mail = wait_new_otp_mail(
        mailbox, since=started, timeout_s=new_timeout_s, seen_uids=seen
    )
    verified = client.post("/auth/verify", json={"email": email, "code": mail.code})
    raise_for_limiter(verified, what="POST /auth/verify")
    if verified.status_code != 200:
        raise ProdHttpError(f"POST /auth/verify returned {verified.status_code}")
    consume_used(mailbox, mail)
    return ProdAuthResult(
        mail=mail,
        set_cookie=verified.headers.get("set-cookie") or "",
    )


def request_new_login_mail(
    client: httpx.Client,
    mailbox: Mailbox,
    email: str,
    *,
    new_timeout_s: float = DEFAULT_NEW_MAIL_TIMEOUT_S,
    now_fn: Callable[[], datetime] = lambda: datetime.now(UTC),
) -> OtpMail:
    seen = snapshot_otp_uids(mailbox)
    started = now_fn()
    request_otp(client, email)
    mail = wait_new_otp_mail(
        mailbox, since=started, timeout_s=new_timeout_s, seen_uids=seen
    )
    parse_login_url(subject=mail.subject, body=mail.body)
    return mail


def consume_login_link(client: httpx.Client, login_url: str) -> ProdLinkResult:
    parsed = urlparse(login_url)
    path = parsed.path
    if not path.startswith("/auth/link/"):
        raise ProdHttpError(f"login URL path is not a login link: {login_url}")
    wash = client.get(path, follow_redirects=False)
    raise_for_limiter(wash, what="GET /auth/link/{token}")
    if wash.status_code not in {302, 303}:
        raise ProdHttpError(f"GET {path} returned {wash.status_code}")
    page = client.get("/auth/link", follow_redirects=False)
    raise_for_limiter(page, what="GET /auth/link")
    posted = client.post("/auth/link", follow_redirects=False)
    raise_for_limiter(posted, what="POST /auth/link")
    if posted.status_code not in {302, 303, 200}:
        raise ProdHttpError(f"POST /auth/link returned {posted.status_code}")
    return ProdLinkResult(
        set_cookie=posted.headers.get("set-cookie") or "",
        confirm_html=page.text,
    )


def smoke_email() -> str:
    load_live_dotenv()
    email = live_email()
    if not email:
        raise ProdHttpError("LIVE_EMAIL or LIVE_IMAP_USER is required")
    return email


def remaining_send_gap_s(
    send_at: datetime, *, now: datetime | None = None, gap_s: float = SEND_GAP_S
) -> float:
    current = now or datetime.now(UTC)
    elapsed = (current - send_at).total_seconds()
    remain = gap_s - elapsed
    return remain if remain > 0 else 0.0
