from __future__ import annotations

from typing import Protocol

from bcra_rag.evals.domain.types import EvalReport, GenerationSample, RetrievalSample


class EvalSink(Protocol):
    def record(
        self,
        report: EvalReport,
        *,
        retrieval: list[RetrievalSample],
        generation: list[GenerationSample],
    ) -> bool: ...
