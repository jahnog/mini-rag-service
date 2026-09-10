from __future__ import annotations

import time

from bcra_rag.domain.guardrails.types import Tracer
from bcra_rag.domain.manifest import Manifest
from bcra_rag.domain.router import Router
from bcra_rag.evals.domain.types import GoldRow, RetrievalSample
from bcra_rag.ports.index import IndexPort


def run_retrieval(
    rows: list[GoldRow],
    index: IndexPort,
    manifest: Manifest,
    *,
    tracer: Tracer,
    k: int = 5,
) -> list[RetrievalSample]:
    router = Router(index, manifest)
    samples: list[RetrievalSample] = []
    for gold in rows:
        span_cm = None
        span = None
        try:
            span_cm = tracer.span("retrieve", "retriever")
            span = span_cm.__enter__()
        except Exception:
            span_cm = None
            span = None
        started = time.perf_counter()
        try:
            result = router.route(gold.question, k=k, to_as_of=manifest.to_as_of)
            latency_ms = (time.perf_counter() - started) * 1000
            retrieved = [str(chunk.metadata.get("doc_id") or "") for chunk in result.hits]
            if result.silencio:
                retrieved = []
                hits = []
            else:
                hits = list(result.hits)
            try:
                tracer.record_retriever(
                    gold.question,
                    hits,
                    route=result.kind or "",
                    silencio_reason=result.silencio_reason if result.silencio else None,
                    span=span,
                )
            except Exception:
                pass
            samples.append(
                RetrievalSample(
                    gold=gold,
                    hits=hits,
                    retrieved_ids=retrieved,
                    latency_ms=latency_ms,
                    silencio=result.silencio,
                )
            )
        finally:
            if span_cm is not None:
                try:
                    span_cm.__exit__(None, None, None)
                except Exception:
                    pass
    return samples
