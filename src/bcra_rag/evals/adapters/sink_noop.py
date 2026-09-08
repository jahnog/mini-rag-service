from __future__ import annotations

from bcra_rag.evals.domain.types import EvalReport, GenerationSample, RetrievalSample


class NoOpEvalSink:
    def record(
        self,
        report: EvalReport,
        *,
        retrieval: list[RetrievalSample],
        generation: list[GenerationSample],
    ) -> bool:
        del report, retrieval, generation
        return False
