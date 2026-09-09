from __future__ import annotations

import time
from datetime import UTC, datetime
from typing import Any

import pytest
from pytest_bdd import given, parsers, then, when

from tests.features.live.http_client import (
    clone_client,
    make_client,
    post_chat,
    post_chat_clear,
    raise_for_limiter,
)
from tests.features.live.mailbox import assert_no_new_otp

LiveWorld = dict[str, Any]


@given("an authenticated live HTTP session", target_fixture="live_world")
def authenticated_live_session(live_http_session: dict[str, Any]) -> LiveWorld:
    return {
        "client": live_http_session["client"],
        "email": live_http_session["email"],
        "code": live_http_session["code"],
        "mailbox": live_http_session["mailbox"],
        "otp_mail": live_http_session["otp_mail"],
        "set_cookie": live_http_session["set_cookie"],
        "response": None,
        "body": None,
        "cloned": None,
    }


@given("no live HTTP session credential", target_fixture="live_world")
def anonymous_live_session(live_anon_client: Any) -> LiveWorld:
    return {
        "client": live_anon_client,
        "email": None,
        "mailbox": None,
        "response": None,
        "body": None,
    }


@given("a live IMAP mailbox without a session credential", target_fixture="live_world")
def mailbox_without_session(
    live_imap_mailbox: Any, live_anon_client: Any
) -> LiveWorld:
    return {
        "client": live_anon_client,
        "mailbox": live_imap_mailbox,
        "request_at": None,
        "response": None,
        "body": None,
    }


@given("live health reports index_ready true")
def live_index_ready(live_world: LiveWorld) -> None:
    response = live_world["client"].get("/health")
    raise_for_limiter(response, what="GET /health")
    body = response.json()
    live_world["health"] = body
    if not body.get("index_ready"):
        pytest.skip("live health reports index_ready false")


@when(parsers.parse('a live client requests a one-time secret for "{email}"'))
def live_request_otp(live_world: LiveWorld, email: str) -> None:
    live_world["request_at"] = datetime.now(UTC)
    response = live_world["client"].post("/auth/request", json={"email": email})
    raise_for_limiter(response, what="POST /auth/request")
    live_world["response"] = response


@when("the live client probes the session")
def live_probe(live_world: LiveWorld) -> None:
    response = live_world["client"].get("/auth/me")
    live_world["response"] = response
    live_world["body"] = response.json()


@when("the live client submits that secret again after the verify interval")
def live_replay_secret(live_world: LiveWorld) -> None:
    time.sleep(2)
    fresh = make_client()
    live_world["replay_client"] = fresh
    response = fresh.post(
        "/auth/verify",
        json={"email": live_world["email"], "code": live_world["code"]},
    )
    raise_for_limiter(response, what="POST /auth/verify replay")
    live_world["response"] = response
    live_world["body"] = fresh.get("/auth/me").json()


@when("the live client logs out on a cloned client")
def live_logout_clone(live_world: LiveWorld) -> None:
    cloned = clone_client(live_world["client"])
    live_world["cloned"] = cloned
    response = cloned.post("/auth/logout")
    raise_for_limiter(response, what="POST /auth/logout")
    live_world["response"] = response


@when("the live client posts a CAMEX question")
def live_unauth_chat(live_world: LiveWorld) -> None:
    response = post_chat(live_world["client"], "Qué es el MULC?")
    live_world["response"] = response


@when("the live client posts chat-clear with a session id")
def live_unauth_clear(live_world: LiveWorld) -> None:
    response = post_chat_clear(live_world["client"])
    live_world["response"] = response


@when("the live client requests health")
def live_health(live_world: LiveWorld) -> None:
    response = live_world["client"].get("/health")
    raise_for_limiter(response, what="GET /health")
    live_world["response"] = response
    live_world["body"] = response.json()


@when(parsers.parse('an authenticated live client posts "{message}"'))
def live_auth_chat(live_world: LiveWorld, message: str) -> None:
    response = post_chat(live_world["client"], message)
    live_world["response"] = response
    live_world["body"] = response.json()


@when("the live client posts authenticated chat-clear")
def live_auth_clear(live_world: LiveWorld) -> None:
    session_id = None
    if live_world.get("body"):
        session_id = live_world["body"].get("session_id")
    response = post_chat_clear(live_world["client"], session_id)
    live_world["response"] = response
    live_world["body"] = response.json()


@then("the live mailbox secret is six digits in the body not the subject")
def live_secret_in_body(live_world: LiveWorld) -> None:
    mail = live_world["otp_mail"]
    assert mail.code == live_world["code"]
    assert len(mail.code) == 6
    assert mail.code.isdigit()
    assert mail.code not in mail.subject
    assert mail.code in mail.body


@then("the live OTP request shape matches success")
def live_otp_ok(live_world: LiveWorld) -> None:
    response = live_world["response"]
    assert response.status_code == 200
    assert response.json() == {"ok": True}


@then("no new live one-time-secret message arrives")
def live_no_new_mail(live_world: LiveWorld) -> None:
    assert_no_new_otp(live_world["mailbox"], since=live_world["request_at"])


@then("the live session probe reports that mailbox")
def live_me_email(live_world: LiveWorld) -> None:
    body = live_world["body"]
    assert live_world["response"].status_code == 200
    assert body["authenticated"] is True
    assert body["email"] == live_world["email"]


@then("the live session cookie is HttpOnly")
def live_cookie_httponly(live_world: LiveWorld) -> None:
    header = live_world["set_cookie"]
    assert "HttpOnly" in header


@then("the live client is not authenticated from that secret")
def live_replay_rejected(live_world: LiveWorld) -> None:
    body = live_world["body"]
    assert body.get("authenticated") is not True


@then("a later live chat request is HTTP 401")
def live_cloned_chat_401(live_world: LiveWorld) -> None:
    response = post_chat(live_world["cloned"], "Qué es el MULC?")
    assert response.status_code == 401


@then("the shared live session remains authenticated")
def live_shared_still_authed(live_world: LiveWorld) -> None:
    me = live_world["client"].get("/auth/me")
    assert me.status_code == 200
    assert me.json()["authenticated"] is True


@then("the live session probe reports unauthenticated")
def live_me_false(live_world: LiveWorld) -> None:
    body = live_world["body"]
    assert body.get("authenticated") is False


@then("the live probe status is not HTTP 401")
def live_me_not_401(live_world: LiveWorld) -> None:
    assert live_world["response"].status_code != 401


@then("the response is HTTP 401")
def live_http_401(live_world: LiveWorld) -> None:
    assert live_world["response"].status_code == 401


@then("the live health response is HTTP 200")
def live_health_200(live_world: LiveWorld) -> None:
    assert live_world["response"].status_code == 200


@then("live health dump fields are present")
def live_health_fields(live_world: LiveWorld) -> None:
    body = live_world["body"]
    for key in ("index_ready", "last_refresh", "to_as_of", "last_comm_id", "n_docs"):
        assert key in body


@then("the live chat response includes the structured contract")
def live_chat_contract(live_world: LiveWorld) -> None:
    assert live_world["response"].status_code == 200
    body = live_world["body"]
    for key in (
        "answer",
        "finding",
        "citations",
        "guardrails",
        "session_id",
        "last_refresh",
        "to_as_of",
    ):
        assert key in body


@then("the HTTP finding is silencio")
def http_finding_silencio(live_world: LiveWorld) -> None:
    assert live_world["body"]["finding"] == "silencio"


@then("the HTTP finding is not silencio")
def http_finding_not_silencio(live_world: LiveWorld) -> None:
    assert live_world["body"]["finding"] != "silencio"


@then("the HTTP no-advice rule is block")
def http_no_advice_block(live_world: LiveWorld) -> None:
    _http_rule(live_world, "no-advice", "block")


@then("the HTTP injection rule is block")
def http_injection_block(live_world: LiveWorld) -> None:
    _http_rule(live_world, "injection", "block")


@then("the HTTP scope rule is block")
def http_scope_block(live_world: LiveWorld) -> None:
    _http_rule(live_world, "scope", "block")


@then("the HTTP answer does not reveal hidden instructions")
def http_no_leak(live_world: LiveWorld) -> None:
    answer = (live_world["body"].get("answer") or "").lower()
    assert "system prompt" not in answer
    assert "quoted clauses stay in spanish" not in answer


@then('an HTTP citation id is "A3500"')
def http_citation_a3500(live_world: LiveWorld) -> None:
    body = live_world["body"]
    if body.get("finding") == "silencio":
        reason = body.get("abstain_reason")
        if reason in {"llm_unavailable", "missing_document"}:
            pytest.skip(f"HTTP finding is silencio with abstain_reason {reason}")
        pytest.fail(f"HTTP finding is silencio with abstain_reason {reason}")
    ids = [item["id"] for item in body.get("citations") or []]
    assert "A3500" in ids


@then("live HTTP citations are empty")
def http_citations_empty(live_world: LiveWorld) -> None:
    assert live_world["body"].get("citations") == []


@then("the acknowledgement has no retrieved citations")
def live_clear_no_citations(live_world: LiveWorld) -> None:
    assert live_world["response"].status_code == 200
    assert live_world["body"].get("citations") == []


def _http_rule(live_world: LiveWorld, name: str, verdict: str) -> None:
    log = live_world["body"]["guardrails"]
    match = next(item for item in log if item["rule"] == name)
    assert match["verdict"] == verdict
