"""The chat_turn log line for one turn."""

from __future__ import annotations

import structlog

from bcra_rag.domain.guardrails import RailContext, RailResult
from bcra_rag.domain.guardrails.input import redact_secrets
from bcra_rag.schemas import ChatRequest, ChatResponse

log = structlog.get_logger(__name__)


def llm_called(response: ChatResponse) -> bool:
    return any(item.rule == "generate" and item.verdict == "pass" for item in response.guardrails)


def blocked_by(response: ChatResponse) -> str | None:
    return next(
        (item.rule for item in response.guardrails if item.verdict == "block" and item.enforced),
        None,
    )


def log_turn(
    request: ChatRequest,
    response: ChatResponse,
    ctx: RailContext,
    results: list[RailResult],
    policy_version: int,
) -> None:
    payload = response.model_dump()
    payload.pop("thinking", None)
    payload["answer"] = redact_secrets(str(payload.get("answer") or ""))
    payload["guardrails"] = [
        {**item, "detail": redact_secrets(str(item.get("detail") or ""))}
        for item in payload.get("guardrails") or []
    ]
    draft = ctx.draft
    log.info(
        "chat_turn",
        message=redact_secrets(request.message or ""),
        k=request.k,
        filters=None if request.filters is None else request.filters.model_dump(),
        llm_called=llm_called(response),
        blocked_by=blocked_by(response),
        policy_version=policy_version,
        guardrail_latency_ms={item.rule: round(item.latency_ms, 3) for item in results},
        survived_ids=sorted(id_ for id_ in ctx.turn_ids if id_),
        dropped_ids=list(ctx.dropped_ids),
        prompt_tokens=draft.prompt_tokens if draft else 0,
        completion_tokens=draft.completion_tokens if draft else 0,
        retrieve_ms=round(ctx.timings.get("retrieve_ms", 0.0), 1),
        llm_ms=round(ctx.timings.get("llm_ms", 0.0), 1),
        ttft_ms=round(draft.ttft_ms, 1) if draft else 0.0,
        thinking_chars=draft.thinking_chars if draft else 0,
        **_route_fields(ctx),
        **payload,
    )


def _route_fields(ctx: RailContext) -> dict[str, object]:
    extra: dict[str, object] = {}
    if ctx.retrieval_route:
        extra["retrieval_route"] = ctx.retrieval_route
    if ctx.named_id:
        extra["named_id"] = ctx.named_id
    if ctx.section_chars is not None:
        extra["section_chars"] = ctx.section_chars
    if ctx.cite_failures is not None:
        draft_finding = ctx.draft.finding if ctx.draft is not None else ctx.finding
        extra["draft_finding"] = draft_finding.value
        extra["draft_citation_ids"] = list(ctx.draft_citation_ids)
        extra["cite_failures"] = ctx.cite_failures
        extra["salvage"] = ctx.salvage or "none"
    return extra
