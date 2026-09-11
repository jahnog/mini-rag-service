"""Collector REST poll for production smoke. Does not import phoenix.client."""

from __future__ import annotations

import os
import time
from collections.abc import Callable, Mapping
from datetime import datetime
from typing import Any

import httpx

from bcra_rag.evals.adapters.sink_phoenix import _collector_host
from tests.features.live.http_client import load_live_dotenv

DEFAULT_POLL_TIMEOUT_S = 180.0
DEFAULT_POLL_S = 1.0
DEFAULT_SPAN_LIMIT = 100
MAX_SPAN_PAGES = 50
CHAT_TURN = "chat.turn"


class PhoenixError(RuntimeError):
    """Collector REST misconfiguration or unexpected response."""


class PhoenixTimeout(PhoenixError):
    """No matching chat.turn span within the poll bound."""


def resolve_api_key(raw: str = "") -> str:
    text = (raw or "").strip()
    if len(text) >= 3 and text.startswith("${") and text.endswith("}"):
        return ""
    if text:
        return text
    load_live_dotenv()
    env = (os.environ.get("PHOENIX_API_KEY") or "").strip()
    if len(env) >= 3 and env.startswith("${") and env.endswith("}"):
        return ""
    return env


def require_phoenix_env() -> tuple[str, str]:
    load_live_dotenv()
    endpoint = (os.environ.get("PROD_PHOENIX_COLLECTOR_ENDPOINT") or "").strip() or (
        os.environ.get("PHOENIX_COLLECTOR_ENDPOINT") or ""
    ).strip()
    project = (os.environ.get("PROD_PHOENIX_PROJECT_NAME") or "").strip()
    if not endpoint:
        raise PhoenixError(
            "PHOENIX_COLLECTOR_ENDPOINT is required "
            "(or PROD_PHOENIX_COLLECTOR_ENDPOINT)"
        )
    if not project:
        raise PhoenixError("PROD_PHOENIX_PROJECT_NAME is required")
    return _collector_host(endpoint), project


def _headers(api_key: str = "") -> dict[str, str]:
    key = resolve_api_key(api_key)
    if not key:
        return {}
    return {"Authorization": f"Bearer {key}"}


def list_spans(
    host: str,
    project: str,
    *,
    name: str | None = None,
    start_time: datetime | str | None = None,
    trace_id: str | None = None,
    api_key: str = "",
    client: httpx.Client | None = None,
    timeout_s: float = 10.0,
    limit: int = DEFAULT_SPAN_LIMIT,
) -> list[dict[str, Any]]:
    params: list[tuple[str, str]] = [("limit", str(limit))]
    if name:
        params.append(("name", name))
    if start_time is not None:
        stamp = (
            start_time
            if isinstance(start_time, str)
            else start_time.isoformat()
        )
        params.append(("start_time", stamp))
    if trace_id:
        params.append(("trace_id", trace_id))
    url = f"{host.rstrip('/')}/v1/projects/{project}/spans"
    own = client is None
    http = client or httpx.Client(timeout=timeout_s)
    items: list[dict[str, Any]] = []
    cursor: str | None = None
    try:
        for _ in range(MAX_SPAN_PAGES):
            page = list(params)
            if cursor:
                page.append(("cursor", cursor))
            response = http.get(url, params=page, headers=_headers(api_key))
            if response.status_code != 200:
                raise PhoenixError(
                    f"GET {url} returned {response.status_code}"
                )
            payload = response.json()
            data = payload.get("data") if isinstance(payload, Mapping) else None
            if not isinstance(data, list):
                raise PhoenixError("collector spans response has no data list")
            items.extend(item for item in data if isinstance(item, dict))
            raw_cursor = (
                payload.get("next_cursor") if isinstance(payload, Mapping) else None
            )
            cursor = str(raw_cursor) if raw_cursor else None
            if not cursor:
                break
    finally:
        if own:
            http.close()
    return items


def span_input_value(span: Mapping[str, Any]) -> str:
    attrs = span.get("attributes") or {}
    if not isinstance(attrs, Mapping):
        return ""
    value = attrs.get("input.value")
    if value is None:
        nested = attrs.get("input")
        if isinstance(nested, Mapping):
            value = nested.get("value")
    return "" if value is None else str(value)


def span_trace_id(span: Mapping[str, Any]) -> str:
    ctx = span.get("context") or {}
    if not isinstance(ctx, Mapping):
        return ""
    return str(ctx.get("trace_id") or "")


def span_name(span: Mapping[str, Any]) -> str:
    return str(span.get("name") or "")


def find_turn_with_child(
    host: str,
    project: str,
    *,
    question: str,
    start_time: datetime,
    child_name: str,
    api_key: str = "",
    client: httpx.Client | None = None,
) -> dict[str, Any] | None:
    turns = list_spans(
        host,
        project,
        name=CHAT_TURN,
        start_time=start_time,
        api_key=api_key,
        client=client,
    )
    needle = question
    for turn in turns:
        if needle not in span_input_value(turn):
            continue
        tid = span_trace_id(turn)
        if not tid:
            continue
        children = list_spans(
            host,
            project,
            trace_id=tid,
            api_key=api_key,
            client=client,
        )
        if any(span_name(child) == child_name for child in children):
            return turn
    return None


def wait_for_turn_with_child(
    host: str,
    project: str,
    *,
    question: str,
    start_time: datetime,
    child_name: str,
    api_key: str = "",
    timeout_s: float = DEFAULT_POLL_TIMEOUT_S,
    poll_s: float = DEFAULT_POLL_S,
    sleep: Callable[[float], None] = time.sleep,
    client: httpx.Client | None = None,
) -> dict[str, Any]:
    deadline = time.monotonic() + timeout_s
    while True:
        found = find_turn_with_child(
            host,
            project,
            question=question,
            start_time=start_time,
            child_name=child_name,
            api_key=api_key,
            client=client,
        )
        if found is not None:
            return found
        if time.monotonic() >= deadline:
            turns = list_spans(
                host,
                project,
                name=CHAT_TURN,
                start_time=start_time,
                api_key=api_key,
                client=client,
            )
            if not turns:
                hint = (
                    "dump host is not exporting to this collector/project"
                )
            else:
                hint = (
                    f"saw {len(turns)} {CHAT_TURN} span(s) but none with "
                    f"{child_name!r} child"
                )
            raise PhoenixTimeout(
                f"no {CHAT_TURN} span with {child_name!r} child for {question!r} "
                f"on {host} project {project}: {hint}"
            )
        sleep(poll_s)
