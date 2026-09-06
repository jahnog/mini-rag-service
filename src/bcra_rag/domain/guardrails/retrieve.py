from __future__ import annotations

import re

from bcra_rag.domain.guardrails.pipeline import ChunkMappingRail
from bcra_rag.domain.guardrails.types import (
    ChunkResult,
    InjectionBackend,
    RailContext,
    RailResult,
    Stage,
)
from bcra_rag.domain.models import Chunk

ROLE_NOISE = re.compile(
    r"(?is)(?:SYSTEM\s*:|<<\s*SYS\s*>>|<\|im_start\|>|<\|im_end\|>|"
    r"<!--.*?-->|ignore previous instructions)"
)


class ChunkHygieneRail(ChunkMappingRail):
    id = "chunk-hygiene"
    stage: Stage = "retrieve"

    def __init__(self, *, enforce: bool = True) -> None:
        self.enforce = enforce

    def inspect(self, chunk: Chunk, ctx: RailContext) -> ChunkResult:
        del ctx
        cleaned = ROLE_NOISE.sub("", chunk.text).strip()
        if cleaned != chunk.text:
            if not cleaned:
                return ChunkResult("drop", chunk, "empty after strip")
            return ChunkResult(
                "redact",
                Chunk(chunk_id=chunk.chunk_id, text=cleaned, metadata=chunk.metadata),
                "stripped role tags",
            )
        return ChunkResult("keep", chunk)


class ChunkInjectionRail(ChunkMappingRail):
    id = "chunk-injection"
    stage: Stage = "retrieve"

    def __init__(self, backend: InjectionBackend, *, enforce: bool = True) -> None:
        self.enforce = enforce
        self._backend = backend

    def inspect(self, chunk: Chunk, ctx: RailContext) -> ChunkResult:
        del ctx
        hit, detail = self._backend.score(chunk.text)
        if hit:
            return ChunkResult("drop", chunk, detail)
        return ChunkResult("keep", chunk)


class ContextBudgetRail:
    id = "context-budget"
    stage: Stage = "retrieve"

    def __init__(self, max_chars: int, *, enforce: bool = True) -> None:
        self.enforce = enforce
        self._max = max_chars

    def run(self, ctx: RailContext) -> RailResult:
        kept: list[Chunk] = []
        used = 0
        dropped = 0
        for chunk in ctx.hits:
            extra = len(chunk.text)
            if kept and used + extra > self._max:
                dropped += 1
                continue
            kept.append(chunk)
            used += extra
        ctx.hits = kept
        if dropped:
            return RailResult(
                rule=self.id,
                stage=self.stage,
                verdict="redact",
                detail=f"dropped {dropped} tail chunks",
                enforced=self.enforce,
            )
        return RailResult(
            rule=self.id,
            stage=self.stage,
            verdict="pass",
            detail=f"kept {len(kept)} chunks",
            enforced=self.enforce,
        )
