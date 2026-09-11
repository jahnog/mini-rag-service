from __future__ import annotations

from datetime import UTC, datetime

import httpx
import pytest
import respx

from bcra_rag.evals.adapters.sink_phoenix import _collector_host
from tests.prod.phoenix import (
    DEFAULT_POLL_TIMEOUT_S,
    PhoenixError,
    PhoenixTimeout,
    require_phoenix_env,
    resolve_api_key,
    wait_for_turn_with_child,
)

HOST = "http://127.0.0.1:6006"
PROJECT = "bcra-rag-prod"
QUESTION = "Qué dice la Comunicación A 3500?"
T0 = datetime(2026, 9, 10, 12, 0, tzinfo=UTC)


def test_host_strip_matches_collector_host() -> None:
    assert DEFAULT_POLL_TIMEOUT_S >= 180
    assert _collector_host("http://127.0.0.1:6006/v1/traces") == HOST
    assert _collector_host("http://127.0.0.1:6006/") == HOST
    assert _collector_host(HOST) == HOST


def test_resolve_api_key_ignores_unexpanded_placeholder(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("PHOENIX_API_KEY", raising=False)
    assert resolve_api_key("${PHOENIX_API_KEY}") == ""
    assert resolve_api_key(" pk-test ") == "pk-test"
    monkeypatch.setenv("PHOENIX_API_KEY", "${PHOENIX_API_KEY}")
    assert resolve_api_key("") == ""
    monkeypatch.setenv("PHOENIX_API_KEY", "pk-env")
    assert resolve_api_key("") == "pk-env"


def test_require_phoenix_env_does_not_use_dev_project(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("PROD_PHOENIX_COLLECTOR_ENDPOINT", raising=False)
    monkeypatch.setenv("PHOENIX_COLLECTOR_ENDPOINT", HOST)
    monkeypatch.setenv("PHOENIX_PROJECT_NAME", "bcra-rag-dev")
    monkeypatch.setenv("PROD_PHOENIX_PROJECT_NAME", "")
    with pytest.raises(PhoenixError, match="PROD_PHOENIX_PROJECT_NAME"):
        require_phoenix_env()
    monkeypatch.setenv("PROD_PHOENIX_PROJECT_NAME", PROJECT)
    host, project = require_phoenix_env()
    assert host == HOST
    assert project == PROJECT


def test_require_phoenix_env_prefers_prod_collector(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("PHOENIX_COLLECTOR_ENDPOINT", HOST)
    monkeypatch.setenv("PROD_PHOENIX_COLLECTOR_ENDPOINT", "http://127.0.0.1:6007")
    monkeypatch.setenv("PROD_PHOENIX_PROJECT_NAME", PROJECT)
    host, project = require_phoenix_env()
    assert host == "http://127.0.0.1:6007"
    assert project == PROJECT


@respx.mock
def test_wait_matches_input_value_and_child(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("PHOENIX_API_KEY", raising=False)
    turn = {
        "name": "chat.turn",
        "context": {"trace_id": "abc", "span_id": "1"},
        "attributes": {"input.value": QUESTION},
    }
    child = {
        "name": "retrieve",
        "context": {"trace_id": "abc", "span_id": "2"},
        "attributes": {},
    }

    def handler(request: httpx.Request) -> httpx.Response:
        params = request.url.params
        if params.get("name") == "chat.turn":
            return httpx.Response(200, json={"data": [turn], "next_cursor": None})
        if params.get("trace_id") == "abc":
            return httpx.Response(
                200, json={"data": [turn, child], "next_cursor": None}
            )
        return httpx.Response(200, json={"data": [], "next_cursor": None})

    respx.get(f"{HOST}/v1/projects/{PROJECT}/spans").mock(side_effect=handler)
    found = wait_for_turn_with_child(
        HOST,
        PROJECT,
        question=QUESTION,
        start_time=T0,
        child_name="retrieve",
        timeout_s=1,
        poll_s=0,
        sleep=lambda _: None,
    )
    assert found["context"]["trace_id"] == "abc"


@respx.mock
def test_wait_sends_bearer_when_key_set(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PHOENIX_API_KEY", "pk-live")
    route = respx.get(f"{HOST}/v1/projects/{PROJECT}/spans").mock(
        return_value=httpx.Response(200, json={"data": [], "next_cursor": None})
    )
    with pytest.raises(PhoenixTimeout):
        wait_for_turn_with_child(
            HOST,
            PROJECT,
            question=QUESTION,
            start_time=T0,
            child_name="retrieve",
            timeout_s=0,
            poll_s=0,
            sleep=lambda _: None,
        )
    assert route.calls[0].request.headers["authorization"] == "Bearer pk-live"


@respx.mock
def test_wait_timeout_and_missing_project() -> None:
    respx.get(f"{HOST}/v1/projects/{PROJECT}/spans").mock(
        return_value=httpx.Response(200, json={"data": [], "next_cursor": None})
    )
    with pytest.raises(PhoenixTimeout):
        wait_for_turn_with_child(
            HOST,
            PROJECT,
            question=QUESTION,
            start_time=T0,
            child_name="scope",
            timeout_s=0,
            poll_s=0,
            sleep=lambda _: None,
        )
    respx.get(f"{HOST}/v1/projects/missing/spans").mock(
        return_value=httpx.Response(404, json={"detail": "not found"})
    )
    with pytest.raises(PhoenixError, match="404"):
        wait_for_turn_with_child(
            HOST,
            "missing",
            question=QUESTION,
            start_time=T0,
            child_name="retrieve",
            timeout_s=0,
            poll_s=0,
            sleep=lambda _: None,
        )


@respx.mock
def test_wait_timeout_names_empty_project() -> None:
    respx.get(f"{HOST}/v1/projects/{PROJECT}/spans").mock(
        return_value=httpx.Response(200, json={"data": [], "next_cursor": None})
    )
    with pytest.raises(
        PhoenixTimeout,
        match="dump host is not exporting to this collector/project",
    ):
        wait_for_turn_with_child(
            HOST,
            PROJECT,
            question=QUESTION,
            start_time=T0,
            child_name="retrieve",
            timeout_s=0,
            poll_s=0,
            sleep=lambda _: None,
        )


@respx.mock
def test_wait_matches_nested_input_value(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("PHOENIX_API_KEY", raising=False)
    turn = {
        "name": "chat.turn",
        "context": {"trace_id": "nested", "span_id": "1"},
        "attributes": {"input": {"value": QUESTION}},
    }
    child = {
        "name": "retrieve",
        "context": {"trace_id": "nested", "span_id": "2"},
        "attributes": {},
    }

    def handler(request: httpx.Request) -> httpx.Response:
        params = request.url.params
        if params.get("name") == "chat.turn":
            return httpx.Response(200, json={"data": [turn], "next_cursor": None})
        if params.get("trace_id") == "nested":
            return httpx.Response(
                200, json={"data": [turn, child], "next_cursor": None}
            )
        return httpx.Response(200, json={"data": [], "next_cursor": None})

    respx.get(f"{HOST}/v1/projects/{PROJECT}/spans").mock(side_effect=handler)
    found = wait_for_turn_with_child(
        HOST,
        PROJECT,
        question=QUESTION,
        start_time=T0,
        child_name="retrieve",
        timeout_s=1,
        poll_s=0,
        sleep=lambda _: None,
    )
    assert found["context"]["trace_id"] == "nested"


@respx.mock
def test_wait_follows_next_cursor(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("PHOENIX_API_KEY", raising=False)
    turn = {
        "name": "chat.turn",
        "context": {"trace_id": "paged", "span_id": "1"},
        "attributes": {"input.value": QUESTION},
    }
    child = {
        "name": "retrieve",
        "context": {"trace_id": "paged", "span_id": "2"},
        "attributes": {},
    }

    def handler(request: httpx.Request) -> httpx.Response:
        params = request.url.params
        assert params.get("limit") == "100"
        if params.get("name") == "chat.turn" and not params.get("cursor"):
            return httpx.Response(
                200, json={"data": [], "next_cursor": "page-2"}
            )
        if params.get("name") == "chat.turn" and params.get("cursor") == "page-2":
            return httpx.Response(200, json={"data": [turn], "next_cursor": None})
        if params.get("trace_id") == "paged":
            return httpx.Response(
                200, json={"data": [turn, child], "next_cursor": None}
            )
        return httpx.Response(200, json={"data": [], "next_cursor": None})

    respx.get(f"{HOST}/v1/projects/{PROJECT}/spans").mock(side_effect=handler)
    found = wait_for_turn_with_child(
        HOST,
        PROJECT,
        question=QUESTION,
        start_time=T0,
        child_name="retrieve",
        timeout_s=1,
        poll_s=0,
        sleep=lambda _: None,
    )
    assert found["context"]["trace_id"] == "paged"
