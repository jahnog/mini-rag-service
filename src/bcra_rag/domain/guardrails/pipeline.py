from __future__ import annotations

import time
from collections.abc import Sequence
from contextlib import AbstractContextManager
from dataclasses import replace
from typing import Any

from bcra_rag.domain.guardrails.types import (
    ChunkAction,
    ChunkResult,
    Rail,
    RailContext,
    RailPatch,
    RailResult,
    Stage,
    Tracer,
)
from bcra_rag.domain.models import Chunk

_ALWAYS_APPLY = frozenset({"normalize"})


class _NullSpan:
    def __enter__(self) -> _NullSpan:
        return self

    def __exit__(self, *args: object) -> None:
        return None

    def set_attribute(self, *_args: object, **_kwargs: object) -> None:
        return None


class NoOpTracer:
    def span(self, name: str, layer: str) -> AbstractContextManager[Any]:
        del name, layer
        return _NullSpan()


class TracedRail:
    def __init__(self, inner: Rail, tracer: Tracer) -> None:
        self._inner = inner
        self._tracer = tracer
        self.id = inner.id
        self.stage = inner.stage
        self.enforce = inner.enforce

    def run(self, ctx: RailContext) -> RailResult:
        started = time.perf_counter()
        span_cm = self._tracer.span(self.id, self.stage)
        with span_cm as span:
            result = self._inner.run(ctx)
            latency_ms = (time.perf_counter() - started) * 1000
            result = replace(result, latency_ms=latency_ms)
            setter = getattr(span, "set_attribute", None)
            if callable(setter):
                setter("openinference.span.kind", "GUARDRAIL")
                setter("guardrail_name", self.id)
                setter("guardrail_layer", self.stage)
                setter("guardrail_decision", result.verdict)
                setter("guardrail_enforced", result.enforced)
                setter("guardrail_latency_ms", result.latency_ms)
            return result


class GuardrailPipeline:
    def __init__(
        self,
        rails: Sequence[Rail],
        *,
        global_enforce: bool = True,
        policy_version: int = 2,
    ) -> None:
        self._rails = list(rails)
        self._global_enforce = global_enforce
        self.policy_version = policy_version

    def enabled(self) -> list[Rail]:
        return list(self._rails)

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
                results.append(_skipped(rail, f"blocked by {blocked_by}"))
                continue
            raw = rail.run(ctx)
            result = _apply_enforce(raw, rail, self._global_enforce)
            if rail.id in _ALWAYS_APPLY or result.enforced:
                _apply_patch(ctx, raw.patch)
            results.append(result)
            if result.enforced and result.verdict == "block":
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


def _apply_enforce(result: RailResult, rail: Rail, global_enforce: bool) -> RailResult:
    enforced = bool(global_enforce and rail.enforce)
    would_block = result.verdict == "block" or result.would_block
    if enforced:
        return replace(result, enforced=True, would_block=would_block)
    verdict = "pass" if result.verdict == "block" else result.verdict
    return replace(result, enforced=False, verdict=verdict, would_block=would_block)


def _skipped(rail: Rail, reason: str) -> RailResult:
    return RailResult(
        rule=rail.id,
        stage=rail.stage,
        verdict="skipped",
        detail=reason,
        enforced=rail.enforce,
        would_block=False,
    )


class ChunkMappingRail:
    id: str
    stage: Stage = "retrieve"
    enforce: bool = True

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
            detail = f"dropped {dropped} of {scanned}"
        elif dropped or redacted:
            verdict = "redact"
            detail = f"scanned {scanned}; dropped {dropped}; redacted {redacted}"
        else:
            verdict = "pass"
            detail = f"scanned {scanned}"
        return RailResult(
            rule=self.id,
            stage="retrieve",
            verdict=verdict,  # type: ignore[arg-type]
            detail=detail,
            enforced=self.enforce,
            would_block=bool(dropped and not kept),
            metrics={"scanned": scanned, "dropped": dropped, "redacted": redacted},
            patch=RailPatch(hits=kept, dropped_ids=dropped_ids),
        )


def step(
    rule: str,
    stage: Stage,
    verdict: str,
    detail: str,
    *,
    enforced: bool = True,
) -> RailResult:
    return RailResult(
        rule=rule,
        stage=stage,
        verdict=verdict,  # type: ignore[arg-type]
        detail=detail,
        enforced=enforced,
        would_block=verdict == "block",
    )
