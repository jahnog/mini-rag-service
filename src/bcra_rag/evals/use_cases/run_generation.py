from __future__ import annotations

import time

from bcra_rag.domain.guardrails import GuardrailPipeline, RailContext
from bcra_rag.domain.health import dump_health
from bcra_rag.evals.domain.types import GenerationSample, GoldRow, RetrievalSample
from bcra_rag.evals.use_cases.oracle import oracle_chunks, usable_oracle
from bcra_rag.ports.index import IndexPort
from bcra_rag.ports.llm import LlmPort
from bcra_rag.schemas import Finding
from bcra_rag.settings import Settings
from bcra_rag.use_cases.answer_query import generate_from_context


async def run_generation(
    rows: list[GoldRow],
    *,
    settings: Settings,
    index: IndexPort,
    llm: LlmPort,
    pipeline: GuardrailPipeline,
    context_source: str,
    retrieval: list[RetrievalSample] | None = None,
) -> list[GenerationSample]:
    health = dump_health(settings, index)
    by_id = {sample.gold.id: sample for sample in retrieval or []}
    samples: list[GenerationSample] = []
    for gold in rows:
        if context_source == "retrieved":
            prior = by_id.get(gold.id)
            context = list(prior.hits) if prior else []
            usable = bool(context)
        else:
            context = oracle_chunks(index, gold, settings)
            usable = usable_oracle(gold, context)
        ctx = RailContext(
            raw=gold.question,
            text=gold.question,
            hits=list(context),
            last_refresh=health.last_refresh,
            to_as_of=health.to_as_of,
        )
        started = time.perf_counter()
        await generate_from_context(llm, pipeline, ctx, gold.question)
        latency_ms = (time.perf_counter() - started) * 1000
        finding = ctx.finding if isinstance(ctx.finding, Finding) else Finding.SILENCIO
        samples.append(
            GenerationSample(
                gold=gold,
                context=context,
                context_source="retrieved" if context_source == "retrieved" else "oracle",
                answer=ctx.answer,
                citations=list(ctx.citations),
                finding=finding,
                latency_ms=latency_ms,
                usable_context=usable,
            )
        )
    return samples
