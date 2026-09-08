from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta

import httpx
import pytest
import respx

from bcra_rag.auth.mail_copy import OTP_SUBJECT, otp_body
from tests.features.live.http_client import (
    LiveHttpError,
    ProcessLimiterError,
    authenticate_from_mailbox,
    browser_headers,
    make_client,
    post_chat,
    post_chat_clear,
    require_origin_match,
)
from tests.features.live.mailbox import FakeMailbox, OtpMail

NOW = datetime(2026, 9, 8, 12, 0, tzinfo=UTC)
BASE = "http://127.0.0.1:8000"


@pytest.fixture
def matching_origin(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AUTH_PUBLIC_ORIGIN", BASE)
    monkeypatch.setenv("LIVE_BASE_URL", BASE)
    monkeypatch.delenv("DEMO_API_KEY", raising=False)


def test_origin_and_referer_headers() -> None:
    headers = browser_headers(BASE)
    assert headers["Origin"] == BASE
    assert headers["Referer"] == f"{BASE}/"
    assert "x-demo-key" not in headers


def test_demo_key_header(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DEMO_API_KEY", "demo-secret")
    headers = browser_headers(BASE)
    assert headers["x-demo-key"] == "demo-secret"


def test_origin_mismatch_names_both_urls() -> None:
    with pytest.raises(LiveHttpError, match="LIVE_BASE_URL") as excinfo:
        require_origin_match(BASE, "https://rag.example")
    message = str(excinfo.value)
    assert BASE in message
    assert "https://rag.example" in message
    assert "AUTH_PUBLIC_ORIGIN" in message


def test_make_client_rejects_origin_mismatch(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LIVE_BASE_URL", BASE)
    monkeypatch.setenv("AUTH_PUBLIC_ORIGIN", "https://rag.example")
    with pytest.raises(LiveHttpError, match="https://rag.example"):
        make_client()


@respx.mock
def test_coalesce_fallback_uses_leftover(matching_origin: None) -> None:
    leftover = OtpMail(
        uid="left",
        subject=OTP_SUBJECT,
        body=otp_body("654321", ttl_s=300),
        date=NOW - timedelta(seconds=30),
        unseen=True,
    )
    box = FakeMailbox([leftover])
    respx.post(f"{BASE}/auth/request").mock(
        return_value=httpx.Response(200, json={"ok": True})
    )
    respx.post(f"{BASE}/auth/verify").mock(
        return_value=httpx.Response(
            200,
            json={"ok": True},
            headers={"set-cookie": "session=tok; HttpOnly; Path=/"},
        )
    )
    client = make_client(BASE)
    auth = authenticate_from_mailbox(
        client,
        box,
        "ops@example.com",
        new_timeout_s=0,
        now_fn=lambda: NOW,
    )
    assert auth.mail.uid == "left"
    assert auth.mail.code == "654321"
    assert "HttpOnly" in auth.set_cookie
    assert auth.sent_new is False
    assert all(item.deleted for item in box.items if item.uid == "left")
    verify = respx.calls[1]
    body = json.loads(verify.request.content)
    assert body == {"email": "ops@example.com", "code": "654321"}
    assert verify.request.headers["origin"] == BASE
    assert verify.request.headers["referer"] == f"{BASE}/"


@respx.mock
def test_chat_429_names_process_limiter(matching_origin: None) -> None:
    respx.post(f"{BASE}/chat").mock(
        return_value=httpx.Response(429, json={"detail": "rate limit exceeded"})
    )
    client = make_client(BASE)
    with pytest.raises(ProcessLimiterError, match="process limiter"):
        post_chat(client, "Qué dice la Comunicación A 3500?")


@respx.mock
def test_unauthenticated_clear_always_sends_session_id(matching_origin: None) -> None:
    route = respx.post(f"{BASE}/chat/clear").mock(
        return_value=httpx.Response(401, json={"detail": "authentication required"})
    )
    client = make_client(BASE)
    response = post_chat_clear(client)
    assert response.status_code == 401
    payload = json.loads(route.calls[0].request.content)
    assert payload["session_id"]
