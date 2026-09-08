from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path
from typing import Any, Literal

import structlog

from bcra_rag.adapters.index_fake import FakeIndex
from bcra_rag.domain.guardrails import GuardrailPipeline
from bcra_rag.domain.guardrails.pipeline import NoOpTracer, span_id_hex
from bcra_rag.domain.guardrails.types import Tracer
from bcra_rag.domain.manifest import Manifest
from bcra_rag.domain.models import Chunk
from bcra_rag.evals.adapters.sink_noop import NoOpEvalSink
from bcra_rag.evals.domain.aggregate import collect, mean, percentile
from bcra_rag.evals.domain.gold import load_gold
from bcra_rag.evals.domain.metrics import (
    AnswerRelevancy,
    CitationIdExact,
    CitationPuntoExact,
    CitationSnippetGrounded,
    ContextPrecision,
    ContextRecall,
    Faithfulness,
    FindingExact,
    HitAtK,
    Mrr,
    NdcgAtK,
    PrecisionAtK,
)
from bcra_rag.evals.domain.types import (
    EvalReport,
    GenerationSample,
    GoldRow,
    RetrievalSample,
    Score,
)
from bcra_rag.evals.ports.judge import Judge
from bcra_rag.evals.ports.sink import EvalSink
from bcra_rag.evals.use_cases.run_generation import run_generation
from bcra_rag.evals.use_cases.run_retrieval import run_retrieval
from bcra_rag.ports.index import IndexPort
from bcra_rag.ports.llm import LlmPort
from bcra_rag.settings import Settings
from bcra_rag.use_cases.rebuild_ab import rebuild_structured_slice

log = structlog.get_logger(__name__)

L1_SCHEMA_KEYS = (
    "unpublished",
    "sample",
    "headline_metric",
    "citation_id_exact",
    "hit_at_5",
    "mrr",
    "retrieval",
    "generation",
    "judge",
    "chunking",
    "slices",
    "phoenix",
    "n",
)

SuiteChoice = Literal["both", "retrieval", "generation"]
ContextChoice = Literal["oracle", "retrieved"]


async def run_l1(
    *,
    gold_path: Path,
    output_path: Path,
    settings: Settings,
    index: IndexPort | None = None,
    llm: LlmPort | None = None,
    pipeline: GuardrailPipeline | None = None,
    manifest: Manifest | None = None,
    judge: Judge | None = None,
    sink: EvalSink | None = None,
    tracer: Tracer | None = None,
    unpublished: bool = True,
    suites: SuiteChoice = "both",
    generation_context: ContextChoice = "oracle",
    deterministic_only: bool = False,
    judge_skip_reason: str | None = None,
    phoenix_project: str = "bcra-rag",
) -> dict[str, Any]:
    rows = load_gold(gold_path)
    resolved_index, manifest = _resolve_index(index, manifest)
    resolved_tracer = tracer or NoOpTracer()
    resolved_sink = sink or NoOpEvalSink()
    active_judge = None if deterministic_only else judge

    annotation_span_id: str | None = None
    span_cm: Any = None
    entered = False
    try:
        span_cm = resolved_tracer.span("eval.l1", "eval")
        span = span_cm.__enter__()
        entered = True
        annotation_span_id = span_id_hex(span)
    except Exception:
        annotation_span_id = None

    try:
        retrieval_samples, generation_samples, retrieval_report, generation_report = (
            await _run_suites(
                rows,
                resolved_index=resolved_index,
                manifest=manifest,
                resolved_tracer=resolved_tracer,
                active_judge=active_judge,
                settings=settings,
                llm=llm,
                pipeline=pipeline,
                suites=suites,
                generation_context=generation_context,
            )
        )
    finally:
        if entered and span_cm is not None:
            try:
                span_cm.__exit__(None, None, None)
            except Exception:
                pass

    slices: dict[str, float]
    grouped_slices: dict[str, list[float]] = defaultdict(list)
    if generation_samples:
        metric = CitationIdExact()
        for gen_sample in generation_samples:
            scored = metric.score(gen_sample)
            grouped_slices[gen_sample.gold.bucket].append(scored.value)
    else:
        metric_hit = HitAtK(5)
        for ret_sample in retrieval_samples:
            grouped_slices[ret_sample.gold.bucket].append(metric_hit.score(ret_sample).value)
    slices = {key: mean(vals) for key, vals in sorted(grouped_slices.items())}

    judge_skipped = active_judge is None
    if deterministic_only:
        skip_reason = "deterministic_only"
    elif judge_skipped:
        skip_reason = judge_skip_reason or "no_judge"
    else:
        skip_reason = None
    if active_judge is None:
        judge_model = "grok-4.3"
        judge_calls = 0
        tokens_in = 0
        tokens_out = 0
    else:
        judge_model = str(getattr(active_judge, "_model", None) or "grok-4.3")
        judge_calls = _usage_count(active_judge, "calls")
        tokens_in = _usage_count(active_judge, "tokens_in")
        tokens_out = _usage_count(active_judge, "tokens_out")
    report = EvalReport(
        unpublished=unpublished,
        sample=unpublished,
        retrieval=retrieval_report,
        generation=generation_report,
        judge_skipped=judge_skipped,
        judge_skip_reason=skip_reason,
        judge_model=judge_model,
        judge_calls=judge_calls,
        tokens_in=tokens_in,
        tokens_out=tokens_out,
        chunking=_chunking(resolved_index),
        slices=slices,
        n=len(rows),
        annotation_span_id=annotation_span_id,
    )
    payload = to_payload(report, phoenix_project=phoenix_project)
    try:
        exported = bool(
            resolved_sink.record(
                report, retrieval=retrieval_samples, generation=generation_samples
            )
        )
        payload["phoenix"]["exported"] = exported
    except Exception:
        payload["phoenix"]["exported"] = False
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    log.info("l1_run", **payload)
    return payload


async def _run_suites(
    rows: list[GoldRow],
    *,
    resolved_index: IndexPort,
    manifest: Manifest,
    resolved_tracer: Tracer,
    active_judge: Judge | None,
    settings: Settings,
    llm: LlmPort | None,
    pipeline: GuardrailPipeline | None,
    suites: SuiteChoice,
    generation_context: ContextChoice,
) -> tuple[list[RetrievalSample], list[GenerationSample], Any, Any]:
    retrieval_samples: list[RetrievalSample] = []
    generation_samples: list[GenerationSample] = []
    retrieval_report = _skipped("not_requested")
    generation_report = _skipped("not_requested")
    if suites in ("both", "retrieval"):
        retrieval_samples = run_retrieval(
            rows, resolved_index, manifest, tracer=resolved_tracer
        )
        retrieval_report = _score_retrieval(retrieval_samples, active_judge)
    if suites in ("both", "generation"):
        if llm is None or pipeline is None:
            generation_report = _skipped("no_llm")
        elif generation_context == "retrieved" and suites != "both":
            generation_report = _skipped("retrieved_context_requires_retrieval")
        else:
            generation_samples = await run_generation(
                rows,
                settings=settings,
                index=resolved_index,
                llm=llm,
                pipeline=pipeline,
                context_source=generation_context,
                retrieval=retrieval_samples,
            )
            generation_report = _score_generation(generation_samples, active_judge)
    return retrieval_samples, generation_samples, retrieval_report, generation_report


def to_payload(report: EvalReport, *, phoenix_project: str = "bcra-rag") -> dict[str, Any]:
    retrieval = report.retrieval
    generation = report.generation
    citation = None if generation.skipped else generation.scores.get("citation_id_exact")
    hit = None if retrieval.skipped else retrieval.scores.get("hit_at_5")
    mrr = None if retrieval.skipped else retrieval.scores.get("mrr")
    return {
        "unpublished": report.unpublished,
        "sample": report.sample,
        "headline_metric": "citation_id_exact",
        "citation_id_exact": citation,
        "hit_at_5": hit,
        "mrr": mrr,
        "retrieval": {
            "skipped": retrieval.skipped,
            "skip_reason": retrieval.skip_reason,
            **retrieval.scores,
            **retrieval.extra,
            "n": retrieval.n,
        },
        "generation": {
            "skipped": generation.skipped,
            "skip_reason": generation.skip_reason,
            **generation.scores,
            **generation.extra,
            "n": generation.n,
        },
        "judge": {
            "model": report.judge_model,
            "skipped": report.judge_skipped,
            "skip_reason": report.judge_skip_reason,
            "calls": report.judge_calls,
            "tokens_in": report.tokens_in,
            "tokens_out": report.tokens_out,
        },
        "chunking": report.chunking,
        "slices": report.slices,
        "phoenix": {
            "exported": report.phoenix_exported,
            "project": phoenix_project,
            "evals_project": None,
        },
        "n": report.n,
    }


def _score_retrieval(samples: list[RetrievalSample], judge: Judge | None) -> Any:
    from bcra_rag.evals.domain.types import SuiteReport

    metrics: list[Any] = [HitAtK(5), PrecisionAtK(5), Mrr(), NdcgAtK(5)]
    if judge is not None:
        metrics.extend([ContextPrecision(judge), ContextRecall(judge)])
    scored: list[Score | None] = []
    for sample in samples:
        for metric in metrics:
            scored.append(metric.score(sample))
    grouped = collect(scored)
    latencies = [sample.latency_ms for sample in samples]
    extras: dict[str, object] = {
        "latency_ms_p50": percentile(latencies, 50),
        "latency_ms_p95": percentile(latencies, 95),
        "n_context_recall": len(grouped.get("context_recall") or []),
    }
    return SuiteReport(
        skipped=False,
        scores={name: mean(vals) for name, vals in grouped.items()},
        n=len(samples),
        extra=extras,
    )


def _score_generation(samples: list[GenerationSample], judge: Judge | None) -> Any:
    from bcra_rag.evals.domain.types import SuiteReport

    metrics: list[Any] = [
        CitationIdExact(),
        CitationPuntoExact(),
        CitationSnippetGrounded(),
        FindingExact(),
    ]
    if judge is not None:
        metrics.extend([Faithfulness(judge), AnswerRelevancy(judge)])
    scored: list[Score | None] = []
    for sample in samples:
        for metric in metrics:
            scored.append(metric.score(sample))
    grouped = collect(scored)
    latencies = [sample.latency_ms for sample in samples]
    source = samples[0].context_source if samples else "oracle"
    extras: dict[str, object] = {
        "context_source": source,
        "latency_ms_p50": percentile(latencies, 50),
        "latency_ms_p95": percentile(latencies, 95),
    }
    return SuiteReport(
        skipped=False,
        scores={name: mean(vals) for name, vals in grouped.items()},
        n=len(samples),
        extra=extras,
    )


def _usage_count(judge: object, name: str) -> int:
    raw = getattr(judge, name, 0)
    if isinstance(raw, int):
        return raw
    if isinstance(raw, list):
        return len(raw)
    try:
        return int(raw or 0)
    except (TypeError, ValueError):
        return 0


def _skipped(reason: str) -> Any:
    from bcra_rag.evals.domain.types import SuiteReport

    return SuiteReport(skipped=True, skip_reason=reason, n=0)


def _chunking(index: IndexPort) -> dict[str, object]:
    extracts: dict[str, tuple[str, dict[str, object]]] = {}
    try:
        text = index.get_section("texto_ordenado")
    except Exception:
        text = ""
    if text.strip():
        extracts["texto_ordenado"] = (text, {"doc_kind": "texto_ordenado"})
    b_chunks = rebuild_structured_slice(extracts, strategy="B") if extracts else []
    a_chunks = rebuild_structured_slice(extracts, strategy="A") if extracts else []
    return {"A": len(a_chunks), "B": len(b_chunks), "b_documents": list(extracts)}


def _resolve_index(
    index: IndexPort | None, manifest: Manifest | None
) -> tuple[IndexPort, Manifest]:
    if index is None:
        seeded = FakeIndex()
        _seed_demo_index(seeded)
        return seeded, manifest or _demo_manifest()
    return index, manifest or Manifest(path=Path("."), to_as_of="A8307")


def _demo_manifest() -> Manifest:
    return Manifest(
        path=Path("."),
        to_as_of="A8307",
        documents={
            "texto_ordenado": {"kind": "texto_ordenado"},
            "A3500": {"kind": "comunicacion", "fecha": "2002-03-08"},
            "A8307": {"kind": "comunicacion", "fecha": "2025-08-25"},
            "A8359": {"kind": "comunicacion", "fecha": "2025-09-01"},
        },
    )


def _seed_demo_index(index: FakeIndex) -> None:
    index.upsert(
        "texto_ordenado",
        [
            Chunk(
                "texto_ordenado:3.8.5:x",
                "Los residentes deberán liquidar el cobro de exportaciones en el MULC.",
                {
                    "doc_kind": "texto_ordenado",
                    "punto": "3.8.5",
                    "chunker": "B",
                    "numero": "texto_ordenado",
                },
            )
        ],
    )
    index.upsert(
        "A3500",
        [
            Chunk(
                "A3500:1",
                "Tipo de cambio de referencia 2002.",
                {
                    "doc_kind": "comunicacion",
                    "fecha": "2002-03-08",
                    "numero": "A3500",
                    "chunker": "A",
                },
            )
        ],
    )
    index.upsert(
        "A8359",
        [
            Chunk(
                "A8359:1",
                "Adecuación del tipo de cambio de referencia posterior al TO.",
                {
                    "doc_kind": "comunicacion",
                    "fecha": "2025-09-01",
                    "numero": "A8359",
                    "chunker": "A",
                },
            )
        ],
    )
