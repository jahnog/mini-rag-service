from __future__ import annotations

from datetime import UTC, datetime, timedelta

import httpx
import pytest
import respx

from bcra_rag.auth.mail_copy import OTP_SUBJECT, otp_body
from tests.features.live.http_client import ProcessLimiterError
from tests.features.live.mailbox import FakeMailbox, MailboxTimeout, OtpMail
from tests.prod.http_client import (
    CHAT_TIMEOUT_S,
    DEFAULT_NEW_MAIL_TIMEOUT_S,
    SEND_GAP_S,
    VERIFY_GAP_S,
    ProdHttpError,
    authenticate_new_from_mailbox,
    consume_login_link,
    make_client,
    post_chat,
    prod_base_url,
    remaining_send_gap_s,
    request_new_login_mail,
    require_origin_match,
    require_prod_ready,
)

NOW = datetime(2026, 9, 8, 12, 0, tzinfo=UTC)
BASE = "https://rag.example"
LOGIN_URL = f"{BASE}/auth/link/tok_abc"
TOKEN_PATH = "/auth/link/tok_abc"
CHAT_OK = {
    "answer": "ok",
    "finding": "definicion",
    "citations": [{"id": "A3500"}],
    "guardrails": [],
    "session_id": "s",
    "last_refresh": "2026-09-08",
    "to_as_of": "2026-09-08",
}
PROXY_502 = (
    '<!DOCTYPE HTML PUBLIC "-//IETF//DTD HTML 2.0//EN">\n'
    "<html><head><title>502 Proxy Error</title></head><body>"
    "<h1>Proxy Error</h1></body></html>\n"
)


@pytest.fixture
def matching_origin(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AUTH_PUBLIC_ORIGIN", BASE)
    monkeypatch.setenv("PROD_BASE_URL", BASE)
    monkeypatch.delenv("DEMO_API_KEY", raising=False)


def test_blank_prod_base_url_is_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PROD_BASE_URL", "  ")
    with pytest.raises(ProdHttpError, match="PROD_BASE_URL is required"):
        prod_base_url()


def test_origin_mismatch_names_both_urls() -> None:
    with pytest.raises(ProdHttpError, match="PROD_BASE_URL") as excinfo:
        require_origin_match(BASE, "http://127.0.0.1:8000")
    message = str(excinfo.value)
    assert BASE in message
    assert "http://127.0.0.1:8000" in message
    assert "AUTH_PUBLIC_ORIGIN" in message


def test_make_client_rejects_origin_mismatch(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PROD_BASE_URL", BASE)
    monkeypatch.setenv("AUTH_PUBLIC_ORIGIN", "http://127.0.0.1:8000")
    with pytest.raises(ProdHttpError, match="127.0.0.1"):
        make_client()


@respx.mock
def test_require_prod_ready_does_not_spawn(matching_origin: None) -> None:
    respx.get(f"{BASE}/health").mock(return_value=httpx.Response(200, json={"ok": True}))
    assert require_prod_ready() == BASE


@respx.mock
def test_authenticate_new_does_not_use_same_timestamp_leftover(
    matching_origin: None,
) -> None:
    leftover = OtpMail(
        uid="left",
        subject=OTP_SUBJECT,
        body=otp_body("654321", ttl_s=300, login_url=LOGIN_URL),
        date=NOW,
        unseen=True,
    )
    box = FakeMailbox([leftover])
    respx.post(f"{BASE}/auth/request").mock(
        return_value=httpx.Response(200, json={"ok": True})
    )
    client = make_client(BASE)
    with pytest.raises(MailboxTimeout):
        authenticate_new_from_mailbox(
            client,
            box,
            "ops@example.com",
            new_timeout_s=0,
            now_fn=lambda: NOW,
        )


@respx.mock
def test_authenticate_new_accepts_clock_skewed_uid(matching_origin: None) -> None:
    arrived = OtpMail(
        uid="skew",
        subject=OTP_SUBJECT,
        body=otp_body("123456", ttl_s=300, login_url=LOGIN_URL),
        date=NOW - timedelta(seconds=3),
        unseen=True,
    )

    class Delayed(FakeMailbox):
        def __init__(self) -> None:
            super().__init__()
            self.hits = 0

        def refresh(self) -> None:
            self.hits += 1
            if self.hits >= 2 and not any(item.uid == "skew" for item in self.items):
                self.add(arrived)

    box = Delayed()
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
    result = authenticate_new_from_mailbox(
        client,
        box,
        "ops@example.com",
        new_timeout_s=1,
        now_fn=lambda: NOW,
    )
    assert result.mail.uid == "skew"
    assert result.mail.code == "123456"


@respx.mock
def test_request_new_login_mail_does_not_use_leftover(matching_origin: None) -> None:
    leftover = OtpMail(
        uid="left",
        subject=OTP_SUBJECT,
        body=otp_body("654321", ttl_s=300, login_url=LOGIN_URL),
        date=NOW,
        unseen=True,
    )
    box = FakeMailbox([leftover])
    respx.post(f"{BASE}/auth/request").mock(
        return_value=httpx.Response(200, json={"ok": True})
    )
    client = make_client(BASE)
    with pytest.raises(MailboxTimeout):
        request_new_login_mail(
            client,
            box,
            "ops@example.com",
            new_timeout_s=0,
            now_fn=lambda: NOW,
        )


@respx.mock
def test_authenticate_new_does_not_use_leftover(matching_origin: None) -> None:
    leftover = OtpMail(
        uid="left",
        subject=OTP_SUBJECT,
        body=otp_body("654321", ttl_s=300, login_url=LOGIN_URL),
        date=NOW - timedelta(seconds=30),
        unseen=True,
    )
    box = FakeMailbox([leftover])
    respx.post(f"{BASE}/auth/request").mock(
        return_value=httpx.Response(200, json={"ok": True})
    )
    client = make_client(BASE)
    with pytest.raises(MailboxTimeout):
        authenticate_new_from_mailbox(
            client,
            box,
            "ops@example.com",
            new_timeout_s=0,
            now_fn=lambda: NOW,
        )


@respx.mock
def test_wash_does_not_follow_redirect(matching_origin: None) -> None:
    respx.get(f"{BASE}{TOKEN_PATH}").mock(
        return_value=httpx.Response(
            302,
            headers={
                "location": "/auth/link",
                "set-cookie": "auth_link=tok_abc; HttpOnly; Path=/auth/link",
            },
        )
    )
    respx.get(f"{BASE}/auth/link").mock(
        return_value=httpx.Response(
            200,
            text="<h1>Iniciar sesión</h1><p>ops@example.com</p>",
        )
    )
    respx.post(f"{BASE}/auth/link").mock(
        return_value=httpx.Response(
            302,
            headers={
                "location": "/",
                "set-cookie": "session=tok; HttpOnly; Secure; Path=/",
            },
        )
    )
    client = make_client(BASE)
    result = consume_login_link(client, LOGIN_URL)
    assert "ops@example.com" in result.confirm_html
    assert "HttpOnly" in result.set_cookie
    assert "Secure" in result.set_cookie
    wash = respx.calls[0].request
    assert wash.method == "GET"
    assert wash.url.path == TOKEN_PATH
    assert [call.request.url.path for call in respx.calls] == [
        TOKEN_PATH,
        "/auth/link",
        "/auth/link",
    ]
    assert respx.calls[2].request.method == "POST"
    assert respx.calls[2].request.headers["origin"] == BASE


@respx.mock
def test_chat_429_names_process_limiter(matching_origin: None) -> None:
    respx.post(f"{BASE}/chat").mock(
        return_value=httpx.Response(429, json={"detail": "rate limit exceeded"})
    )
    client = make_client(BASE)
    with pytest.raises(ProcessLimiterError, match="process limiter"):
        post_chat(client, "Qué dice la Comunicación A 3500?")
    assert len(respx.calls) == 1


@respx.mock
def test_chat_retries_502_then_json(matching_origin: None) -> None:
    respx.post(f"{BASE}/chat").mock(
        side_effect=[
            httpx.Response(502, text=PROXY_502),
            httpx.Response(200, json=CHAT_OK),
        ]
    )
    client = make_client(BASE)
    response = post_chat(
        client, "Qué dice la Comunicación A 3500?", sleep=lambda _: None
    )
    assert response.status_code == 200
    assert response.json()["citations"][0]["id"] == "A3500"
    assert len(respx.calls) == 2


@respx.mock
def test_chat_502_names_status_not_json_decode(matching_origin: None) -> None:
    respx.post(f"{BASE}/chat").mock(return_value=httpx.Response(502, text=PROXY_502))
    client = make_client(BASE)
    with pytest.raises(ProdHttpError, match="502") as excinfo:
        post_chat(client, "Qué dice la Comunicación A 3500?", sleep=lambda _: None)
    assert "JSONDecodeError" not in type(excinfo.value).__name__
    assert "Proxy Error" in str(excinfo.value)
    assert len(respx.calls) == 3


def test_remaining_send_gap() -> None:
    assert remaining_send_gap_s(NOW, now=NOW + timedelta(seconds=10), gap_s=60) == 50
    assert remaining_send_gap_s(NOW, now=NOW + timedelta(seconds=90), gap_s=60) == 0
    assert SEND_GAP_S > 60
    assert VERIFY_GAP_S >= 2.0
    assert DEFAULT_NEW_MAIL_TIMEOUT_S >= 180
    assert CHAT_TIMEOUT_S >= 480
    assert remaining_send_gap_s(NOW, now=NOW, gap_s=VERIFY_GAP_S) == VERIFY_GAP_S
    assert remaining_send_gap_s(
        NOW, now=NOW + timedelta(seconds=VERIFY_GAP_S), gap_s=VERIFY_GAP_S
    ) == 0
