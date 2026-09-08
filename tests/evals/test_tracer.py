from __future__ import annotations

from collections.abc import Sequence
from contextlib import AbstractContextManager
from typing import Any

from bcra_rag.adapters.otel import retriever_attributes
from bcra_rag.domain.guardrails.pipeline import span_id_hex
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
        self.retriever_calls: list[tuple[str, list[Chunk]]] = []

    def span(self, name: str, layer: str) -> Any:
        del name, layer
        return _SpanCM(self.last)

    def record_retriever(self, query: str, hits: Sequence[Chunk]) -> None:
        self.retriever_calls.append((query, list(hits)))
        for key, value in retriever_attributes(query, hits).items():
            self.last.set_attribute(key, value)


def test_retriever_attributes_are_flat_openinference() -> None:
    hits = [Chunk("A3500:1", "tipo de cambio", {"doc_id": "A3500", "score": 0.9})]
    attrs = retriever_attributes("Qué dice A 3500?", hits)
    assert attrs["openinference.span.kind"] == "RETRIEVER"
    assert attrs["retrieval.documents.0.document.id"] == "A3500"
    assert attrs["retrieval.documents.0.document.content"] == "tipo de cambio"
    assert attrs["retrieval.documents.0.document.score"] == 0.9
    assert "retrieval.documents" not in attrs


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


def test_record_retriever_sets_openinference_kind() -> None:
    tracer = RecordingTracer()
    hits = [Chunk("A3500:1", "tipo de cambio", {"doc_id": "A3500", "score": 0.9})]
    tracer.record_retriever("Qué dice A 3500?", hits)
    assert tracer.last.attrs["openinference.span.kind"] == "RETRIEVER"
    assert tracer.last.attrs["retrieval.documents.0.document.id"] == "A3500"
