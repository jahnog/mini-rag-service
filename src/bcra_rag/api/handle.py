"""Gate in front of one chat turn.

Requires the email session cookie, then the rate limit and the daily turn
caps. The session id is bound to the mailbox, so
one person's history is not another's. AnswerQuery runs only after that.
"""

from __future__ import annotations

import hashlib
import hmac
from dataclasses import dataclass
from uuid import uuid4

import structlog
from fastapi import HTTPException

from bcra_rag.api.rate_limit import RateLimiter
from bcra_rag.api.turn_caps import TurnCaps
from bcra_rag.auth import AuthModule, email_from_request
from bcra_rag.auth.ip import client_ip
from bcra_rag.domain.guardrails import GuardrailPipeline
from bcra_rag.ports.index import IndexPort
from bcra_rag.ports.llm import LlmPort, OnThinking
from bcra_rag.ports.session import SessionStore
from bcra_rag.schemas import ChatFilters, ChatRequest, ChatResponse
from bcra_rag.settings import Settings
from bcra_rag.use_cases.answer_query import AnswerQuery
from bcra_rag.use_cases.generate import OnPhase

_log = structlog.get_logger("bcra_rag.chat")


@dataclass(frozen=True)
class PreparedTurn:
    email: str
    public_id: str
    scoped_id: str


def prepare_turn(
    *,
    settings: Settings,
    limiter: RateLimiter,
    turn_caps: TurnCaps,
    auth: AuthModule,
    request: object,
    message: str,
    session_id: str | None,
    k: int | None,
    client_id: str,
) -> PreparedTurn:
    email = email_from_request(auth, request)
    if email is None:
        raise HTTPException(status_code=401, detail="authentication required")
    if not limiter.allow(client_id):
        raise HTTPException(status_code=429, detail="rate limit exceeded")
    if (message or "").strip().lower() != "/clear":
        blocked = turn_caps.allow(email)
        if blocked is not None:
            prefix = hashlib.sha256(email.encode()).hexdigest()[:8]
            _log.info("chat_cap", email_hash=prefix, outcome=blocked)
            raise HTTPException(status_code=429, detail="rate limit exceeded")
    if k is not None and k > settings.max_k:
        raise HTTPException(status_code=422, detail="k exceeds maximum")
    public_id = _public_session_id(session_id)
    return PreparedTurn(
        email=email,
        public_id=public_id,
        scoped_id=_scoped_session_id(email, public_id, auth.settings.secret),
    )


async def run_prepared_turn(
    prepared: PreparedTurn,
    *,
    settings: Settings,
    index: IndexPort,
    llm: LlmPort,
    sessions: SessionStore,
    pipeline: GuardrailPipeline,
    message: str,
    k: int | None,
    filters: ChatFilters | None,
    request_id: str,
    on_thinking: OnThinking | None = None,
    thinking: bool | None = None,
    on_phase: OnPhase | None = None,
    turn_caps: TurnCaps | None = None,
) -> ChatResponse:
    use_case = AnswerQuery(settings, index, llm, sessions, pipeline)
    response = await use_case.run(
        ChatRequest(
            message=message, session_id=prepared.scoped_id, k=k, filters=filters
        ),
        request_id=request_id,
        on_thinking=on_thinking,
        thinking=thinking,
        on_phase=on_phase,
    )
    if turn_caps is not None and (message or "").strip().lower() != "/clear":
        blocked_input = any(
            item.stage == "input" and item.verdict == "block" and item.enforced
            for item in response.guardrails
        )
        if blocked_input:
            turn_caps.release(prepared.email)
            prefix = hashlib.sha256(prepared.email.encode()).hexdigest()[:8]
            _log.info("chat_cap_refund", email_hash=prefix)
    return response.model_copy(update={"session_id": prepared.public_id})


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
    request: object,
    message: str,
    session_id: str | None,
    k: int | None,
    filters: ChatFilters | None,
    request_id: str,
    client_id: str,
    on_thinking: OnThinking | None = None,
    thinking: bool | None = None,
    on_phase: OnPhase | None = None,
) -> ChatResponse:
    prepared = prepare_turn(
        settings=settings,
        limiter=limiter,
        turn_caps=turn_caps,
        auth=auth,
        request=request,
        message=message,
        session_id=session_id,
        k=k,
        client_id=client_id,
    )
    return await run_prepared_turn(
        prepared,
        settings=settings,
        index=index,
        llm=llm,
        sessions=sessions,
        pipeline=pipeline,
        message=message,
        k=k,
        filters=filters,
        request_id=request_id,
        on_thinking=on_thinking,
        thinking=thinking,
        on_phase=on_phase,
        turn_caps=turn_caps,
    )


def _public_session_id(session_id: str | None) -> str:
    raw = (session_id or "").strip()
    return raw or str(uuid4())


def _scoped_session_id(email: str, public_id: str, secret: str) -> str:
    payload = f"{email}|{public_id}".encode()
    return hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()


def client_id_for(request: object, *, trusted_proxy: bool = False) -> str:
    return client_ip(request, trusted_proxy=trusted_proxy)
