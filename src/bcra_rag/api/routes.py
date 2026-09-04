from __future__ import annotations

from typing import Any, cast

from fastapi import FastAPI, Request
from structlog.contextvars import bind_contextvars, clear_contextvars

from bcra_rag.api.handle import client_id_for, demo_key_for, handle_turn
from bcra_rag.api.rate_limit import RateLimiter
from bcra_rag.domain.health import dump_health
from bcra_rag.ports.index import IndexPort
from bcra_rag.ports.llm import LlmPort
from bcra_rag.ports.session import SessionStore
from bcra_rag.schemas import ChatClearRequest, ChatRequest, ChatResponse, HealthResponse
from bcra_rag.settings import Settings


def create_fastapi(
    *,
    settings: Settings,
    index: IndexPort,
    llm: LlmPort,
    sessions: SessionStore,
) -> FastAPI:
    api = FastAPI(title="BCRA Mini-RAG", version="0.1.0")
    api.state.settings = settings
    api.state.index = index
    api.state.llm = llm
    api.state.sessions = sessions
    api.state.limiter = RateLimiter(
        max_requests=settings.rate_limit_requests,
        window_s=settings.rate_limit_window_s,
    )

    @api.middleware("http")
    async def request_id_middleware(request: Request, call_next: Any) -> Any:
        request_id = request.headers.get("x-request-id") or _new_request_id()
        bind_contextvars(request_id=request_id)
        request.state.request_id = request_id
        try:
            response = await call_next(request)
            response.headers["x-request-id"] = request_id
            return response
        finally:
            clear_contextvars()

    @api.get("/health", response_model=HealthResponse)
    def health() -> HealthResponse:
        return dump_health(settings, index)

    @api.post("/chat", response_model=ChatResponse)
    async def chat(payload: ChatRequest, request: Request) -> ChatResponse:
        return await handle_turn(
            settings=settings,
            index=index,
            llm=llm,
            sessions=sessions,
            limiter=api.state.limiter,
            message=payload.message,
            session_id=payload.session_id,
            k=payload.k,
            filters=payload.filters,
            request_id=getattr(request.state, "request_id", "unknown"),
            client_id=client_id_for(request),
            demo_key=demo_key_for(request),
        )

    @api.post("/chat/clear", response_model=ChatResponse)
    async def chat_clear(payload: ChatClearRequest, request: Request) -> ChatResponse:
        return await handle_turn(
            settings=settings,
            index=index,
            llm=llm,
            sessions=sessions,
            limiter=api.state.limiter,
            message="/clear",
            session_id=payload.session_id,
            k=None,
            filters=None,
            request_id=getattr(request.state, "request_id", "unknown"),
            client_id=client_id_for(request),
            demo_key=demo_key_for(request),
        )

    from bcra_rag.ui.gradio_app import build_blocks, mount_ui

    blocks = build_blocks(
        settings=settings,
        index=index,
        llm=llm,
        sessions=sessions,
        limiter=api.state.limiter,
    )
    return cast(FastAPI, mount_ui(api, blocks))


def _new_request_id() -> str:
    import uuid

    return str(uuid.uuid4())
