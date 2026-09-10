from __future__ import annotations

from collections.abc import Sequence
from contextlib import AbstractContextManager
from pathlib import Path
from typing import Any

import pytest

from bcra_rag.adapters.otel import (
    phoenix_register_kwargs,
    resolve_collector_endpoint,
    resolve_project_name,
    retriever_attributes,
)
from bcra_rag.domain.guardrails.pipeline import TracedRail, span_id_hex
from bcra_rag.domain.guardrails.types import RailContext, RailResult
from bcra_rag.domain.models import Chunk


class _Span:
    def __init__(self) -> None:
        self.attrs: dict[str, object] = {}

    def set_attribute(self, key: str, value: object) -> None:
        self.attrs[key] = value


class _SpanCM(AbstractContextManager[_Span]):
    def __init__(self, span: _Span) -> None:
        self._span = span

    def __enter__(self) -> _Span:
        return self._span

    def __exit__(self, *args: object) -> None:
        return None


class RecordingTracer:
    def __init__(self) -> None:
        self.last = _Span()
        self.names: list[tuple[str, str]] = []
        self.spans: dict[str, _Span] = {}
        self.retriever_calls: list[tuple[str, list[Chunk]]] = []

    def span(self, name: str, layer: str) -> Any:
        self.last = _Span()
        self.names.append((name, layer))
        self.spans[name] = self.last
        return _SpanCM(self.last)

    def record_retriever(
        self,
        query: str,
        hits: Sequence[Chunk],
        *,
        route: str = "",
        silencio_reason: str | None = None,
        span: Any = None,
    ) -> None:
        self.retriever_calls.append((query, list(hits)))
        target = span or self.last
        for key, value in retriever_attributes(
            query, hits, route=route, silencio_reason=silencio_reason
        ).items():
            target.set_attribute(key, value)
        self.last = target

    def record_tokens(self, prompt_tokens: int, completion_tokens: int) -> None:
        target = self.spans.get("chat.turn") or self.last
        target.set_attribute("metadata.prompt_tokens", prompt_tokens)
        target.set_attribute("metadata.completion_tokens", completion_tokens)
        target.set_attribute(
            "metadata.total_tokens", prompt_tokens + completion_tokens
        )

    def record_scores(self, span: Any, scores: object) -> None:
        target = span or self.last
        for name, value in dict(scores or {}).items():
            target.set_attribute(f"eval.{name}", value)


def test_retriever_attributes_are_flat_openinference() -> None:
    hits = [
        Chunk(
            "A3500:1",
            "tipo de cambio",
            {"doc_id": "A3500", "score": 0.9, "punto": "1", "chunker": "A"},
        )
    ]
    attrs = retriever_attributes("Qué dice A 3500?", hits, route="named")
    assert attrs["openinference.span.kind"] == "RETRIEVER"
    assert attrs["retrieval.route"] == "named"
    assert attrs["retrieval.documents.0.document.id"] == "A3500"
    assert attrs["retrieval.documents.0.document.content"] == "tipo de cambio"
    assert attrs["retrieval.documents.0.document.score"] == 0.9
    assert attrs["output.value"] == "A3500"
    assert '"punto": "1"' in str(attrs["retrieval.documents.0.document.metadata"])
    assert "retrieval.documents" not in attrs


def test_empty_retriever_output_uses_silencio_reason() -> None:
    attrs = retriever_attributes("q", [], silencio_reason="missing_document")
    assert attrs["output.value"] == "missing_document"


def test_retriever_content_is_capped() -> None:
    hits = [Chunk("A1:1", "x" * 2000, {"doc_id": "A1"})]
    attrs = retriever_attributes("q", hits)
    content = str(attrs["retrieval.documents.0.document.content"])
    assert len(content) == 800


def test_span_id_hex_formats_otel_context() -> None:
    class _Ctx:
        def __init__(self, span_id: int) -> None:
            self.span_id = span_id

    class _SpanWithCtx:
        def __init__(self, span_id: int) -> None:
            self._span_id = span_id

        def get_span_context(self) -> _Ctx:
            return _Ctx(self._span_id)

    assert span_id_hex(_SpanWithCtx(0xAB)) == "00000000000000ab"
    assert span_id_hex(object()) is None


def test_phoenix_register_kwargs_include_api_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("PHOENIX_API_KEY", raising=False)
    monkeypatch.delenv("PHOENIX_PROJECT_NAME", raising=False)
    with_key = phoenix_register_kwargs("http://127.0.0.1:6006", api_key=" pk-test ")
    assert with_key["api_key"] == "pk-test"
    monkeypatch.setenv("PHOENIX_API_KEY", "pk-env")
    from_env = phoenix_register_kwargs("http://127.0.0.1:6006")
    assert from_env["api_key"] == "pk-env"
    monkeypatch.delenv("PHOENIX_API_KEY", raising=False)
    empty = phoenix_register_kwargs("http://127.0.0.1:6006", api_key="")
    assert "api_key" not in empty
    assert empty["endpoint"] == "http://127.0.0.1:6006/v1/traces"
    already = phoenix_register_kwargs("http://127.0.0.1:6006/v1/traces", api_key="")
    assert already["endpoint"] == "http://127.0.0.1:6006/v1/traces"
    assert empty["protocol"] == "http/protobuf"
    assert empty["batch"] is True
    unexpanded = phoenix_register_kwargs(
        "http://127.0.0.1:6006", api_key="${PHOENIX_API_KEY}"
    )
    assert "api_key" not in unexpanded


def test_record_retriever_sets_openinference_kind() -> None:
    tracer = RecordingTracer()
    hits = [Chunk("A3500:1", "tipo de cambio", {"doc_id": "A3500", "score": 0.9})]
    tracer.record_retriever("Qué dice A 3500?", hits, route="named")
    assert tracer.last.attrs["openinference.span.kind"] == "RETRIEVER"
    assert tracer.last.attrs["retrieval.documents.0.document.id"] == "A3500"
    assert tracer.last.attrs["retrieval.route"] == "named"


def test_resolve_collector_endpoint_prefers_explicit_then_env(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.delenv("PHOENIX_COLLECTOR_ENDPOINT", raising=False)
    env_file = tmp_path / ".env"
    env_file.write_text("PHOENIX_COLLECTOR_ENDPOINT=http://from-file:6006\n", encoding="utf-8")
    assert (
        resolve_collector_endpoint(explicit=" http://explicit:6006 ")
        == "http://explicit:6006"
    )
    monkeypatch.setenv("PHOENIX_COLLECTOR_ENDPOINT", "http://from-env:6006")
    assert resolve_collector_endpoint(env_file=env_file) == "http://from-env:6006"
    monkeypatch.delenv("PHOENIX_COLLECTOR_ENDPOINT", raising=False)
    from_file = resolve_collector_endpoint(env_file=env_file, allow_env_file=True)
    assert from_file == "http://from-file:6006"
    skipped = resolve_collector_endpoint(env_file=env_file, allow_env_file=False)
    assert skipped == ""
    env_file.write_text("PHOENIX_PROJECT_NAME=from-file\n", encoding="utf-8")
    monkeypatch.delenv("PHOENIX_PROJECT_NAME", raising=False)
    assert resolve_project_name(env_file=env_file, allow_env_file=True) == "from-file"
    assert resolve_project_name(explicit="explicit") == "explicit"


def test_traced_rail_sets_output_and_would_block() -> None:
    class _Block:
        id = "scope"
        stage = "input"
        enforce = True

        def run(self, ctx: RailContext) -> RailResult:
            del ctx
            return RailResult(
                rule="scope",
                stage="input",
                verdict="block",
                detail="weather",
                would_block=True,
            )

    tracer = RecordingTracer()
    result = TracedRail(_Block(), tracer).run(RailContext(raw="q", text="q"))
    assert result.verdict == "block"
    assert tracer.last.attrs["openinference.span.kind"] == "GUARDRAIL"
    assert tracer.last.attrs["output.value"] == "block"
    assert tracer.last.attrs["guardrail_would_block"] is True
    assert tracer.last.attrs["guardrail_detail"] == "weather"
    assert "input.value" not in tracer.last.attrs
