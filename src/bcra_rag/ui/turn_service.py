"""The page's one entry point into the answer path, shared by chat and clear."""

from __future__ import annotations

from dataclasses import dataclass

import gradio as gr

from bcra_rag.api.handle import client_id_for, handle_turn
from bcra_rag.api.rate_limit import RateLimiter
from bcra_rag.api.turn_caps import TurnCaps
from bcra_rag.auth import AuthModule
from bcra_rag.domain.guardrails import GuardrailPipeline
from bcra_rag.domain.turn_eval import TurnEvaluator
from bcra_rag.ports.index import IndexPort
from bcra_rag.ports.llm import LlmPort, OnThinking
from bcra_rag.ports.session import SessionStore
from bcra_rag.schemas import ChatResponse
from bcra_rag.settings import Settings
from bcra_rag.use_cases.answer_query import OnPhase, new_request_id


@dataclass(frozen=True)
class TurnService:
    """Holds the collaborators `handle_turn` needs, so callers only pass the per-turn data.

    The page runs turns through the same `handle_turn` path as POST /chat.
    """

    settings: Settings
    index: IndexPort
    llm: LlmPort
    sessions: SessionStore
    pipeline: GuardrailPipeline
    limiter: RateLimiter
    turn_caps: TurnCaps
    auth: AuthModule
    turn_evaluator: TurnEvaluator

    async def run_chat_turn(
        self,
        *,
        gradio_request: gr.Request,
        message: str,
        session_id: str | None,
        demo_key: str | None,
        thinking: bool | None = None,
        on_thinking: OnThinking | None = None,
        on_phase: OnPhase | None = None,
    ) -> ChatResponse:
        """Answer one message (or run a command such as `/clear`) for this browser request."""
        return await handle_turn(
            settings=self.settings,
            index=self.index,
            llm=self.llm,
            sessions=self.sessions,
            pipeline=self.pipeline,
            limiter=self.limiter,
            turn_caps=self.turn_caps,
            auth=self.auth,
            request=gradio_request,
            message=message,
            session_id=session_id or None,
            k=None,
            filters=None,
            request_id=new_request_id(),
            client_id=client_id_for(
                gradio_request, trusted_proxy=self.auth.settings.trust_proxy
            ),
            demo_key=demo_key,
            on_thinking=on_thinking,
            turn_evaluator=self.turn_evaluator,
            thinking=thinking,
            on_phase=on_phase,
        )
