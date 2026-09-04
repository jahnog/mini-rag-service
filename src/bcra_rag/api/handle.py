from __future__ import annotations

from typing import Any

from fastapi import HTTPException

from bcra_rag.api.rate_limit import RateLimiter
from bcra_rag.ports.index import IndexPort
from bcra_rag.ports.llm import LlmPort
from bcra_rag.ports.session import SessionStore
from bcra_rag.schemas import ChatFilters, ChatRequest, ChatResponse
from bcra_rag.settings import Settings
from bcra_rag.use_cases.answer_query import AnswerQuery


async def handle_turn(
    *,
    settings: Settings,
    index: IndexPort,
    llm: LlmPort,
    sessions: SessionStore,
    limiter: RateLimiter,
    message: str,
    session_id: str | None,
    k: int | None,
    filters: ChatFilters | None,
    request_id: str,
    client_id: str,
    demo_key: str | None,
) -> ChatResponse:
    if settings.demo_api_key and demo_key != settings.demo_api_key:
        raise HTTPException(status_code=401, detail="invalid demo key")
    if not limiter.allow(client_id):
        raise HTTPException(status_code=429, detail="rate limit exceeded")
    if k is not None and k > settings.max_k:
        raise HTTPException(status_code=422, detail="k exceeds maximum")
    use_case = AnswerQuery(settings, index, llm, sessions)
    return await use_case.run(
        ChatRequest(message=message, session_id=session_id, k=k, filters=filters),
        request_id=request_id,
    )


def client_id_for(request: Any) -> str:
    forwarded = _header(request, "x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    client = getattr(request, "client", None)
    host = getattr(client, "host", None) if client is not None else None
    if host:
        return str(host)
    return "unknown"


def demo_key_for(request: Any) -> str | None:
    return _header(request, "x-demo-key") or _bearer(request)


def _header(request: Any, name: str) -> str | None:
    headers = getattr(request, "headers", None)
    if headers is None:
        return None
    getter = getattr(headers, "get", None)
    if callable(getter):
        value = getter(name) or getter(name.title()) or getter(name.upper())
        return str(value) if value else None
    return None


def _bearer(request: Any) -> str | None:
    header = _header(request, "authorization") or ""
    if header.lower().startswith("bearer "):
        return header[7:].strip()
    return None
