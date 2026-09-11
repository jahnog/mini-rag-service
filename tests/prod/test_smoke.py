from __future__ import annotations

import time
from collections.abc import Iterator
from datetime import UTC, datetime
from typing import Any
from urllib.parse import urlparse

import httpx
import pytest

from tests.features.live.http_client import raise_for_limiter
from tests.features.live.mailbox import ImapMailbox, consume_used
from tests.prod.http_client import (
    VERIFY_GAP_S,
    ProdHttpError,
    authenticate_new_from_mailbox,
    consume_login_link,
    make_client,
    post_chat,
    prod_base_url,
    remaining_send_gap_s,
    request_new_login_mail,
    smoke_email,
)
from tests.prod.phoenix import require_phoenix_env, wait_for_turn_with_child

pytestmark = pytest.mark.prod_smoke

A3500 = "Qué dice la Comunicación A 3500?"
WEATHER = "What's the weather in Madrid?"
HEALTH_KEYS = (
    "index_ready",
    "last_refresh",
    "to_as_of",
    "last_comm_id",
    "n_docs",
)
CONTRACT_KEYS = (
    "answer",
    "finding",
    "citations",
    "guardrails",
    "session_id",
    "last_refresh",
    "to_as_of",
)


@pytest.fixture(scope="session")
def prod_health() -> Iterator[dict[str, Any]]:
    client = make_client()
    try:
        response = client.get("/health")
        raise_for_limiter(response, what="GET /health")
        if response.status_code != 200:
            raise ProdHttpError(f"GET /health returned {response.status_code}")
        body = response.json()
        missing = [key for key in HEALTH_KEYS if key not in body]
        if missing:
            raise ProdHttpError(f"GET /health missing {missing}")
        if not body.get("index_ready"):
            raise ProdHttpError("index_ready is false")
        yield body
    finally:
        client.close()


@pytest.fixture(scope="session")
def prod_imap_mailbox() -> Iterator[ImapMailbox]:
    box = ImapMailbox()
    try:
        yield box
    finally:
        box.close()


@pytest.fixture(scope="session")
def prod_otp_session(
    prod_imap_mailbox: ImapMailbox,
) -> Iterator[dict[str, Any]]:
    client = make_client()
    email = smoke_email()
    send1_at = datetime.now(UTC)
    auth = authenticate_new_from_mailbox(client, prod_imap_mailbox, email)
    try:
        yield {
            "client": client,
            "email": email,
            "auth": auth,
            "send1_at": send1_at,
        }
    finally:
        client.close()


@pytest.fixture(scope="session")
def prod_chats(prod_otp_session: dict[str, Any]) -> dict[str, Any]:
    client = prod_otp_session["client"]
    t0 = datetime.now(UTC)
    named = post_chat(client, A3500)
    weather = post_chat(client, WEATHER)
    return {
        "t0": t0,
        "named": named,
        "named_body": named.json(),
        "weather": weather,
        "weather_body": weather.json(),
    }


@pytest.fixture(scope="session")
def prod_traces(prod_chats: dict[str, Any]) -> dict[str, Any]:
    host, project = require_phoenix_env()
    t0 = prod_chats["t0"]
    with httpx.Client(timeout=10.0) as http:
        named_span = wait_for_turn_with_child(
            host,
            project,
            question=A3500,
            start_time=t0,
            child_name="retrieve",
            client=http,
        )
        weather_span = wait_for_turn_with_child(
            host,
            project,
            question=WEATHER,
            start_time=t0,
            child_name="scope",
            client=http,
        )
    return {"named": named_span, "weather": weather_span}


@pytest.fixture(scope="session")
def prod_link_session(
    prod_otp_session: dict[str, Any],
    prod_imap_mailbox: ImapMailbox,
) -> Iterator[dict[str, Any]]:
    remain = remaining_send_gap_s(prod_otp_session["send1_at"])
    if remain:
        time.sleep(remain)
    email = prod_otp_session["email"]
    mail = request_new_login_mail(
        prod_otp_session["client"], prod_imap_mailbox, email
    )
    browser = make_client()
    try:
        result = consume_login_link(browser, mail.login_url)
        consume_used(prod_imap_mailbox, mail)
        yield {
            "client": browser,
            "email": email,
            "mail": mail,
            "result": result,
            "confirmed_at": datetime.now(UTC),
        }
    finally:
        browser.close()


def test_health_is_ready(prod_health: dict[str, Any]) -> None:
    for key in HEALTH_KEYS:
        assert key in prod_health
    assert prod_health["index_ready"] is True


def test_otp_authenticates(prod_otp_session: dict[str, Any]) -> None:
    client = prod_otp_session["client"]
    email = prod_otp_session["email"]
    auth = prod_otp_session["auth"]
    me = client.get("/auth/me")
    raise_for_limiter(me, what="GET /auth/me")
    body = me.json()
    assert me.status_code == 200
    assert body["authenticated"] is True
    assert body["email"] == email
    header = auth.set_cookie
    assert "HttpOnly" in header
    if urlparse(prod_base_url()).scheme.lower() == "https":
        assert "Secure" in header
    assert auth.mail.code.isdigit() and len(auth.mail.code) == 6
    assert auth.mail.code not in auth.mail.subject
    assert "/auth/link/" in auth.mail.login_url


def test_named_a3500(prod_chats: dict[str, Any]) -> None:
    response = prod_chats["named"]
    body = prod_chats["named_body"]
    assert response.status_code == 200
    for key in CONTRACT_KEYS:
        assert key in body
    if body.get("finding") == "silencio":
        pytest.fail(
            "HTTP finding is silencio with abstain_reason "
            f"{body.get('abstain_reason')}"
        )
    ids = [item["id"] for item in body.get("citations") or []]
    assert "A3500" in ids


def test_weather_is_out_of_scope(prod_chats: dict[str, Any]) -> None:
    response = prod_chats["weather"]
    body = prod_chats["weather_body"]
    assert response.status_code == 200
    for key in CONTRACT_KEYS:
        assert key in body
    assert body["finding"] == "silencio"
    match = next(item for item in body["guardrails"] if item["rule"] == "scope")
    assert match["verdict"] == "block"


def test_collector_received_turns(prod_traces: dict[str, Any]) -> None:
    assert prod_traces["named"]["name"] == "chat.turn"
    assert A3500 in str(
        (prod_traces["named"].get("attributes") or {}).get("input.value")
    )
    assert prod_traces["weather"]["name"] == "chat.turn"
    assert WEATHER in str(
        (prod_traces["weather"].get("attributes") or {}).get("input.value")
    )


def test_login_link_confirms(prod_link_session: dict[str, Any]) -> None:
    client = prod_link_session["client"]
    email = prod_link_session["email"]
    result = prod_link_session["result"]
    mail = prod_link_session["mail"]
    assert email in result.confirm_html
    me = client.get("/auth/me")
    raise_for_limiter(me, what="GET /auth/me")
    body = me.json()
    assert me.status_code == 200
    assert body["authenticated"] is True
    assert body["email"] == email
    remain = remaining_send_gap_s(
        prod_link_session["confirmed_at"], gap_s=VERIFY_GAP_S
    )
    if remain:
        time.sleep(remain)
    replay = make_client()
    try:
        replayed = replay.post(
            "/auth/verify", json={"email": email, "code": mail.code}
        )
        raise_for_limiter(replayed, what="POST /auth/verify replay")
        probe = replay.get("/auth/me")
        assert probe.json().get("authenticated") is not True
    finally:
        replay.close()
