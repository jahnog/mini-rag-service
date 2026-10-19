"""Run the ordered guardrail checks for one turn.

A rail is one check. run_named runs a named list in order and applies each
rail's patch. The default short-circuit logs later rails as skipped after a
block and does not run them. Output calls this with short-circuit off.
"""

from __future__ import annotations

import time
from collections.abc import Sequence
from dataclasses import replace

from bcra_rag.domain.guardrails.copy import detail_label
from bcra_rag.domain.guardrails.types import (
    ChunkAction,
    ChunkResult,
    Rail,
    RailContext,
    RailPatch,
    RailResult,
    Stage,
)
from bcra_rag.domain.models import Chunk


class GuardrailPipeline:
    def __init__(self, rails: Sequence[Rail]) -> None:
        self._rails = list(rails)

    def ids_for(self, stage: Stage) -> list[str]:
        return [rail.id for rail in self._rails if rail.stage == stage]

    def run_named(
        self,
        ids: Sequence[str],
        ctx: RailContext,
        *,
        short_circuit: bool = True,
    ) -> list[RailResult]:
        wanted = list(ids)
        by_id = {rail.id: rail for rail in self._rails}
        results: list[RailResult] = []
        blocked_by: str | None = None
        for name in wanted:
            rail = by_id.get(name)
            if rail is None:
                continue
            if short_circuit and blocked_by is not None:
                results.append(_skipped(rail, detail_label(f"blocked by {blocked_by}")))
                continue
            started = time.perf_counter()
            result = replace(rail.run(ctx), latency_ms=(time.perf_counter() - started) * 1000)
            _apply_patch(ctx, result.patch)
            results.append(result)
            if result.verdict == "block":
                blocked_by = result.rule
        return results

    def skip_named(self, ids: Sequence[str], reason: str) -> list[RailResult]:
        by_id = {rail.id: rail for rail in self._rails}
        results: list[RailResult] = []
        for name in ids:
            rail = by_id.get(name)
            if rail is not None:
                results.append(_skipped(rail, reason))
        return results

    def skip_stage(self, stage: Stage, reason: str) -> list[RailResult]:
        return [_skipped(rail, reason) for rail in self._rails if rail.stage == stage]


def _apply_patch(ctx: RailContext, patch: RailPatch | None) -> None:
    if patch is None:
        return
    if patch.raw is not None:
        ctx.raw = patch.raw
    if patch.text is not None:
        ctx.text = patch.text
    if patch.answer is not None:
        ctx.answer = patch.answer
    if patch.finding is not None:
        ctx.finding = patch.finding
    if patch.citations is not None:
        ctx.citations = patch.citations
    if patch.hits is not None:
        ctx.hits = patch.hits
    if patch.dropped_ids:
        ctx.dropped_ids.extend(patch.dropped_ids)


def _skipped(rail: Rail, reason: str) -> RailResult:
    return RailResult(
        rule=rail.id,
        stage=rail.stage,
        verdict="skipped",
        detail=reason,
    )


class ChunkMappingRail:
    """Keep, redact, or drop each retrieved passage. Dropping every passage is a block."""

    id: str
    stage: Stage = "retrieve"

    def inspect(self, chunk: Chunk, ctx: RailContext) -> ChunkResult:
        raise NotImplementedError

    def run(self, ctx: RailContext) -> RailResult:
        kept: list[Chunk] = []
        dropped_ids: list[str] = []
        dropped = 0
        redacted = 0
        scanned = 0
        for chunk in ctx.hits:
            scanned += 1
            item = self.inspect(chunk, ctx)
            action: ChunkAction = item.action
            if action == "drop":
                dropped += 1
                dropped_ids.append(str(chunk.metadata.get("doc_id") or chunk.chunk_id))
                continue
            if action == "redact":
                redacted += 1
                kept.append(item.chunk)
                continue
            kept.append(item.chunk)
        if dropped and not kept:
            verdict: str = "block"
            detail = f"se descartaron {dropped} de {scanned}"
        elif dropped or redacted:
            verdict = "redact"
            detail = f"revisados {scanned}; descartados {dropped}; recortados {redacted}"
        else:
            verdict = "pass"
            detail = f"revisados {scanned}"
        return RailResult(
            rule=self.id,
            stage="retrieve",
            verdict=verdict,  # type: ignore[arg-type]
            detail=detail,
            patch=RailPatch(hits=kept, dropped_ids=dropped_ids),
        )


def step(
    rule: str,
    stage: Stage,
    verdict: str,
    detail: str,
) -> RailResult:
    return RailResult(
        rule=rule,
        stage=stage,
        verdict=verdict,  # type: ignore[arg-type]
        detail=detail,
    )
