from __future__ import annotations

import time

from bcra_rag.domain.manifest import Manifest
from bcra_rag.domain.router import Router
from bcra_rag.evals.domain.types import GoldRow, RetrievalSample
from bcra_rag.ports.index import IndexPort


def run_retrieval(
    rows: list[GoldRow],
    index: IndexPort,
    manifest: Manifest,
    *,
    k: int = 5,
) -> list[RetrievalSample]:
    """Score search with the same Router as chat.

    Recorded ids are metadata["doc_id"]. A silencio route records none, so
    hit@k is 1 only when gold also has no ids.
    """
    router = Router(index, manifest)
    samples: list[RetrievalSample] = []
    for gold in rows:
        started = time.perf_counter()
        result = router.route(gold.question, k=k, to_as_of=manifest.to_as_of)
        latency_ms = (time.perf_counter() - started) * 1000
        hits = [] if result.silencio else list(result.hits)
        samples.append(
            RetrievalSample(
                gold=gold,
                hits=hits,
                retrieved_ids=[str(chunk.metadata.get("doc_id") or "") for chunk in hits],
                latency_ms=latency_ms,
                silencio=result.silencio,
            )
        )
    return samples
