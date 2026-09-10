from __future__ import annotations

import hashlib
import hmac
from typing import Any
from uuid import uuid4

import structlog
from fastapi import HTTPException

from bcra_rag.api.rate_limit import RateLimiter
from bcra_rag.api.turn_caps import TurnCaps
from bcra_rag.auth import AuthModule, email_from_request
from bcra_rag.auth.ip import client_ip
from bcra_rag.domain.guardrails import GuardrailPipeline
from bcra_rag.domain.turn_eval import NoOpTurnEvaluator, TurnEvaluator
from bcra_rag.ports.index import IndexPort
from bcra_rag.ports.llm import LlmPort, OnThinking
from bcra_rag.ports.session import SessionStore
from bcra_rag.schemas import ChatFilters, ChatRequest, ChatResponse
from bcra_rag.settings import Settings
from bcra_rag.use_cases.answer_query import AnswerQuery

_log = structlog.get_logger("bcra_rag.chat")


async def handle_turn(
    *,
    settings: Settings,
    index: IndexPort,
    llm: LlmPort,
    sessions: SessionStore,
    pipeline: GuardrailPipeline,
    limiter: RateLimiter,
    turn_caps: TurnCaps,
    auth: AuthModule,
    request: Any,
    message: str,
    session_id: str | None,
    k: int | None,
    filters: ChatFilters | None,
    request_id: str,
    client_id: str,
    demo_key: str | None,
    on_thinking: OnThinking | None = None,
    turn_evaluator: TurnEvaluator | None = None,
) -> ChatResponse:
    email = email_from_request(auth, request)
    if email is None:
        raise HTTPException(status_code=401, detail="authentication required")
    if settings.demo_api_key and demo_key != settings.demo_api_key:
        raise HTTPException(status_code=401, detail="invalid demo key")
    if (message or "").strip().lower() != "/clear":
        blocked = turn_caps.allow(email)
        if blocked is not None:
            prefix = hashlib.sha256(email.encode()).hexdigest()[:8]
            _log.info("chat_cap", email_hash=prefix, outcome=blocked)
            raise HTTPException(status_code=429, detail="rate limit exceeded")
    if not limiter.allow(client_id):
        raise HTTPException(status_code=429, detail="rate limit exceeded")
    if k is not None and k > settings.max_k:
        raise HTTPException(status_code=422, detail="k exceeds maximum")
    public_id = _public_session_id(session_id)
    scoped_id = _scoped_session_id(email, public_id, auth.settings.secret)
    use_case = AnswerQuery(
        settings,
        index,
        llm,
        sessions,
        pipeline,
        evaluator=turn_evaluator or NoOpTurnEvaluator(),
    )
    response = await use_case.run(
        ChatRequest(message=message, session_id=scoped_id, k=k, filters=filters),
        request_id=request_id,
        on_thinking=on_thinking,
    )
    return response.model_copy(update={"session_id": public_id})


def _public_session_id(session_id: str | None) -> str:
    raw = (session_id or "").strip()
    return raw or str(uuid4())


def _scoped_session_id(email: str, public_id: str, secret: str) -> str:
    payload = f"{email}|{public_id}".encode()
    return hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()


def client_id_for(request: Any, *, trusted_proxy: bool = False) -> str:
    return client_ip(request, trusted_proxy=trusted_proxy)


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
