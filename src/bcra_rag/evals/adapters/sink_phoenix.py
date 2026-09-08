from __future__ import annotations

from typing import Any
from urllib.parse import urlparse, urlunparse

from bcra_rag.evals.domain.types import EvalReport, GenerationSample, RetrievalSample

_CODE_METRICS = frozenset(
    {
        "hit_at_5",
        "precision_at_5",
        "mrr",
        "ndcg_at_5",
        "citation_id_exact",
        "citation_punto_exact",
        "citation_snippet_grounded",
        "finding_exact",
    }
)


class PhoenixEvalSink:
    def __init__(self, endpoint: str, project: str, client: Any | None = None) -> None:
        self._base = _collector_host(endpoint)
        self._project = project
        self._client = client

    def record(
        self,
        report: EvalReport,
        *,
        retrieval: list[RetrievalSample],
        generation: list[GenerationSample],
    ) -> bool:
        del retrieval, generation
        span_id = report.annotation_span_id
        if not span_id:
            return False
        client = self._client
        if client is None:
            from phoenix.client import Client

            client = Client(base_url=self._base)
        annotations: list[dict[str, object]] = []
        annotations.extend(
            _annotations("retrieval", report.retrieval.scores, span_id)
        )
        annotations.extend(
            _annotations("generation", report.generation.scores, span_id)
        )
        if not annotations:
            return False
        log = getattr(getattr(client, "spans", None), "log_span_annotations", None)
        if not callable(log):
            return False
        log(span_annotations=annotations)
        return True


def _annotations(
    prefix: str, scores: dict[str, float], span_id: str
) -> list[dict[str, object]]:
    items: list[dict[str, object]] = []
    for name, value in scores.items():
        kind = "CODE" if name in _CODE_METRICS else "LLM"
        items.append(
            {
                "span_id": span_id,
                "name": f"{prefix}.{name}",
                "annotator_kind": kind,
                "result": {"score": value},
            }
        )
    return items


def _collector_host(endpoint: str) -> str:
    text = endpoint.strip().rstrip("/")
    if text.endswith("/v1/traces"):
        text = text[: -len("/v1/traces")]
    parsed = urlparse(text)
    if not parsed.scheme:
        return text
    return urlunparse((parsed.scheme, parsed.netloc, "", "", "", ""))
