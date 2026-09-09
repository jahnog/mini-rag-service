from __future__ import annotations

from bcra_rag.evals.adapters.sink_phoenix import (
    PhoenixEvalSink,
    _collector_host,
    phoenix_client_kwargs,
)
from bcra_rag.evals.domain.types import EvalReport, SuiteReport


class _Spans:
    def __init__(self) -> None:
        self.posted: list[list[dict[str, object]]] = []

    def log_span_annotations(
        self, span_annotations: list[dict[str, object]] | None = None, **_kwargs: object
    ) -> None:
        self.posted.append(list(span_annotations or []))


class _Client:
    def __init__(self) -> None:
        self.spans = _Spans()
        self.constructed = True


def _report(**kwargs: object) -> EvalReport:
    payload = {
        "unpublished": True,
        "sample": True,
        "retrieval": SuiteReport(scores={"hit_at_5": 1.0}),
        "generation": SuiteReport(scores={"faithfulness": 0.5, "citation_id_exact": 0.2}),
        "annotation_span_id": "abc123",
    }
    payload.update(kwargs)
    return EvalReport(**payload)  # type: ignore[arg-type]


def test_collector_host_strips_otlp_path() -> None:
    assert _collector_host("http://127.0.0.1:6006/v1/traces") == "http://127.0.0.1:6006"
    assert _collector_host("http://127.0.0.1:6006/") == "http://127.0.0.1:6006"
    assert _collector_host("http://127.0.0.1:6006") == "http://127.0.0.1:6006"


def test_phoenix_sink_posts_namespaced_span_bound_annotations() -> None:
    client = _Client()
    sink = PhoenixEvalSink("http://127.0.0.1:6006", "bcra-rag", client=client)
    exported = sink.record(_report(), retrieval=[], generation=[])
    assert exported is True
    posted = client.spans.posted[0]
    assert posted
    assert all(item["span_id"] == "abc123" for item in posted)
    names = {str(item["name"]) for item in posted}
    assert "retrieval.hit_at_5" in names
    assert "generation.faithfulness" in names
    assert all(
        str(item["name"]).startswith("retrieval.")
        or str(item["name"]).startswith("generation.")
        for item in posted
    )
    by_name = {str(item["name"]): item for item in posted}
    assert by_name["retrieval.hit_at_5"]["annotator_kind"] == "CODE"
    assert by_name["generation.faithfulness"]["annotator_kind"] == "LLM"
    assert by_name["generation.citation_id_exact"]["annotator_kind"] == "CODE"


def test_phoenix_client_kwargs_omit_empty_api_key() -> None:
    with_key = phoenix_client_kwargs("http://127.0.0.1:6006", " secret ")
    assert with_key == {"base_url": "http://127.0.0.1:6006", "api_key": "secret"}
    empty = phoenix_client_kwargs("http://127.0.0.1:6006", "")
    assert empty == {"base_url": "http://127.0.0.1:6006", "api_key": None}


def test_phoenix_sink_skips_client_without_span_id() -> None:
    client = _Client()
    sink = PhoenixEvalSink("http://127.0.0.1:6006", "bcra-rag", client=client)
    exported = sink.record(
        _report(annotation_span_id=None), retrieval=[], generation=[]
    )
    assert exported is False
    assert client.spans.posted == []
