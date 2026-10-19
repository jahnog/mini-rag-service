"""One chat turn: search the CAMEX dump, then ask the model to cite a clause.

RAG here does not answer from model memory. It searches a local index of BCRA
CAMEX passages, puts those passages in the prompt, and requires a citation.

A chunk is one stored passage. A hit is a chunk the search returned. A citation
id is metadata["doc_id"] (a Comunicación or texto ordenado), never chunk_id.

Silencio is a deliberate abstention: an input block, a missing or empty
document, an empty search, a citation that does not anchor, or an output block.

Guardrails are deterministic checks in stages input, retrieve, generate, and
output. Each rail's verdict stands and its patch is applied. Input and
retrieve stop after a block and log the rest as skipped. Output rails all
run; a block there changes the answer.

The turn runs as stages, each of which may end it early with silencio: gate
(input rails, /clear, index ready), retrieve, then generate (see generate.py).
"""

from __future__ import annotations

import asyncio
import re
import time
from dataclasses import dataclass, field, replace
from uuid import uuid4

import structlog

from bcra_rag.domain.disclaimer import disclaimer_for
from bcra_rag.domain.freeze import freeze_footer
from bcra_rag.domain.guardrails import GuardrailPipeline, RailContext, RailResult, step
from bcra_rag.domain.guardrails.copy import NO_CLAUSE, blocked_copy, detail_label
from bcra_rag.domain.guardrails.types import first_block
from bcra_rag.domain.health import dump_health
from bcra_rag.domain.manifest import Manifest
from bcra_rag.domain.router import Router, RouteResult, named_ids
from bcra_rag.ports.index import IndexPort
from bcra_rag.ports.llm import LlmPort
from bcra_rag.ports.session import SessionStore
from bcra_rag.schemas import ChatRequest, ChatResponse, Finding, HealthResponse, Sidecar
from bcra_rag.settings import Settings
from bcra_rag.use_cases.citations import build_sidecar
from bcra_rag.use_cases.generate import (
    PHASE_RETRIEVE,
    GenerateOptions,
    OnPhase,
    emit,
    generate_from_context,
    history_block,
)
from bcra_rag.use_cases.turn_log import log_turn

FOLLOW_RE = re.compile(r"^\s*(y|and|ese|esa|eso|that|el punto)\b", re.IGNORECASE)
CLEAR_RE = re.compile(r"^\s*/clear\s*$", re.IGNORECASE)
_INPUT_PREFIX = ("length", "normalize")
log = structlog.get_logger(__name__)


def new_request_id() -> str:
    return str(uuid4())


@dataclass
class _Turn:
    """State shared by the stages of one turn."""

    request: ChatRequest
    request_id: str
    session_id: str
    health: HealthResponse
    ctx: RailContext
    log: list[RailResult] = field(default_factory=list)
    history: list[tuple[str, str]] = field(default_factory=list)


class AnswerQuery:
    def __init__(
        self,
        settings: Settings,
        index: IndexPort,
        llm: LlmPort,
        sessions: SessionStore,
        pipeline: GuardrailPipeline,
    ) -> None:
        self._settings = settings
        self._index = index
        self._llm = llm
        self._sessions = sessions
        self._pipeline = pipeline

    async def run(
        self,
        request: ChatRequest,
        *,
        request_id: str,
        thinking: bool | None = None,
        on_phase: OnPhase | None = None,
    ) -> ChatResponse:
        options = GenerateOptions(
            timeout_s=self._settings.llm_timeout_s,
            on_phase=on_phase,
            thinking=thinking,
            chunk_chars=self._settings.context_chunk_chars,
        )
        turn = await self._start(request, request_id)
        return await self._respond(turn, options)

    async def _start(self, request: ChatRequest, request_id: str) -> _Turn:
        health = await asyncio.to_thread(dump_health, self._settings, self._index)
        message = request.message or ""
        ctx = RailContext(
            raw=message,
            text=message,
            last_refresh=health.last_refresh,
            to_as_of=health.to_as_of,
        )
        session_id = request.session_id or self._sessions.mint()
        return _Turn(request, request_id, session_id, health, ctx)

    async def _respond(self, turn: _Turn, options: GenerateOptions) -> ChatResponse:
        """Run the stages in order; the first one that abstains ends the turn."""
        early = self._gate(turn)
        if early is None:
            early = await self._retrieve(turn, options.on_phase)
        if early is not None:
            return early
        return await self._generate(turn, options)

    def _gate(self, turn: _Turn) -> ChatResponse | None:
        """Input rails, /clear, follow-up glue, and index readiness.

        length and normalize see the raw message. Scope and no-advice still
        read raw after the follow-up is glued into text. Injection scores text.
        A block or a cleared session returns silencio before any search.
        """
        pipe = self._pipeline
        input_ids = pipe.ids_for("input")
        if CLEAR_RE.match(turn.request.message or ""):
            self._sessions.clear(turn.session_id)
            skipped = self._skipped(input_ids, detail_label("cleared"))
            return self._abstain(turn, "Sesión borrada.", skipped, "cleared")

        prefix = [name for name in input_ids if name in _INPUT_PREFIX]
        suffix = [name for name in input_ids if name not in _INPUT_PREFIX]
        pre = pipe.run_named(prefix, turn.ctx)
        turn.log += pre
        if blocked := first_block(pre):
            return self._blocked(turn, blocked, skip=suffix)

        turn.history = self._sessions.get(turn.session_id)
        composed = _compose_followup(turn.ctx.text, turn.history)
        turn.ctx.followup = composed != turn.ctx.text
        turn.ctx.text = composed
        post = pipe.run_named(suffix, turn.ctx)
        turn.log += post
        if blocked := first_block(post):
            return self._blocked(turn, blocked, skip=[])

        if not turn.health.index_ready:
            skipped = self._skipped([], detail_label("index_not_ready"))
            return self._abstain(turn, "El índice no está listo.", skipped, "index_not_ready")
        return None

    async def _retrieve(self, turn: _Turn, on_phase: OnPhase | None) -> ChatResponse | None:
        """Route and search, then run the retrieve rails.

        Empty route, no hits, or every passage dropped: silencio, and the model
        is not called. A nearest passage is a candidate, not yet an answer.
        """
        pipe = self._pipeline
        ctx = turn.ctx
        retrieve_ids = pipe.ids_for("retrieve")
        routed = await self._route(turn, on_phase)
        if routed.silencio or not routed.hits:
            reason = routed.silencio_reason or "empty_hits"
            shown = detail_label(reason)
            rest = (
                [step("retrieve", "retrieve", "block", shown)]
                + pipe.skip_named(retrieve_ids, shown)
                + [step("generate", "generate", "skipped", shown)]
            )
            sidecar = build_sidecar(routed.hits, [])
            return self._abstain(turn, NO_CLAUSE, rest, reason, sidecar)

        ctx.hits = list(routed.hits)
        count = step("retrieve", "retrieve", "pass", f"{len(ctx.hits)} fragmentos")
        turn.log += [count, *pipe.run_named(retrieve_ids, ctx)]
        if ctx.hits:
            return None
        rest = [step("generate", "generate", "skipped", detail_label("retrieve_empty"))]
        sidecar = build_sidecar(routed.hits, [])
        return self._abstain(turn, NO_CLAUSE, rest, "retrieve_empty", sidecar)

    async def _route(self, turn: _Turn, on_phase: OnPhase | None) -> RouteResult:
        ctx = turn.ctx
        manifest = Manifest.load_cached(self._settings.manifest_path)
        started = time.perf_counter()
        await emit(on_phase, PHASE_RETRIEVE)
        try:
            routed = await asyncio.to_thread(
                Router(self._index, manifest).route,
                ctx.text,
                k=self._settings.default_k,
                to_as_of=manifest.to_as_of or turn.health.to_as_of,
            )
        finally:
            ctx.timings["retrieve_ms"] = (time.perf_counter() - started) * 1000
        ctx.dump_ids = set(manifest.documents)
        ctx.retrieval_route = routed.kind
        ctx.named_id = routed.named_id
        if routed.kind == "named":
            ctx.section_chars = len(routed.hits[0].text) if routed.hits else 0
        return routed

    async def _generate(self, turn: _Turn, options: GenerateOptions) -> ChatResponse:
        """The model drafts from the passages only; output rails then accept, adjust, or hide it."""
        ctx = turn.ctx
        manifest = Manifest.load_cached(self._settings.manifest_path)
        options = replace(
            options, doc_meta=manifest.documents, history=history_block(turn.history)
        )
        generated = await generate_from_context(
            self._llm, self._pipeline, ctx, ctx.text, options
        )
        turn.log += generated.log
        if generated.draft is None:
            return self._finalize(turn, ctx.generate_reason or "llm_unavailable")
        blocked = generated.blocked
        return self._finalize(
            turn,
            blocked.rule if blocked else None,
            sidecar=build_sidecar(ctx.hits, ctx.citations),
            extra_log=generated.output_log,
            thinking=(generated.draft.thinking or "").strip() or None,
        )

    def _skipped(self, input_names: list[str], detail: str) -> list[RailResult]:
        """Log rows for everything a stopped turn did not run."""
        pipe = self._pipeline
        return (
            pipe.skip_named(input_names, detail)
            + pipe.skip_stage("retrieve", detail)
            + [step("retrieve", "retrieve", "skipped", detail)]
            + [step("generate", "generate", "skipped", detail)]
        )

    def _blocked(self, turn: _Turn, blocked: RailResult, *, skip: list[str]) -> ChatResponse:
        skipped = self._skipped(skip, detail_label(f"blocked by {blocked.rule}"))
        reason = "message_too_long" if blocked.rule == "length" else blocked.rule
        return self._abstain(turn, blocked_copy(blocked.rule), skipped, reason)

    def _abstain(
        self,
        turn: _Turn,
        answer: str,
        rest: list[RailResult],
        reason: str,
        sidecar: Sidecar | None = None,
    ) -> ChatResponse:
        turn.ctx.finding = Finding.SILENCIO
        turn.ctx.answer = answer
        turn.log += rest
        return self._finalize(turn, reason, sidecar=sidecar)

    def _finalize(
        self,
        turn: _Turn,
        abstain_reason: str | None,
        *,
        sidecar: Sidecar | None = None,
        extra_log: list[RailResult] | None = None,
        thinking: str | None = None,
    ) -> ChatResponse:
        """Build the response the side panel renders, including the guardrail log.

        Paths that never generated append the dump footer here, then run output
        rails (those calls short-circuit). A generated turn already did both.
        A turn that searched (it has a sidecar) is remembered for follow-ups.
        """
        ctx = turn.ctx
        if extra_log is None:
            ctx.answer = f"{ctx.answer} {freeze_footer(ctx.last_refresh, ctx.to_as_of)}"
            extra_log = self._pipeline.run_named(self._pipeline.ids_for("output"), ctx)
        results = turn.log + extra_log
        silencio = ctx.finding is Finding.SILENCIO
        response = ChatResponse(
            answer=ctx.answer,
            finding=ctx.finding,
            citations=ctx.citations,
            abstain=silencio,
            abstain_reason=abstain_reason if silencio else None,
            last_refresh=ctx.last_refresh,
            to_as_of=ctx.to_as_of,
            guardrails=[item.to_verdict() for item in results],
            sidecar=sidecar or Sidecar(),
            request_id=turn.request_id,
            session_id=turn.session_id,
            disclaimer=disclaimer_for(ctx.last_refresh),
            thinking=thinking,
        )
        if sidecar is not None:
            self._sessions.append(turn.session_id, "user", turn.request.message)
            self._sessions.append(turn.session_id, "assistant", response.answer)
        log_turn(turn.request, response, ctx, results)
        return response


def _is_short_followup(message: str) -> bool:
    words = message.split()
    return 0 < len(words) <= 3 and not named_ids(message)


def _compose_followup(message: str, history: list[tuple[str, str]]) -> str:
    """Glue a short follow-up (y, ese, el punto, …) onto the previous question before search."""
    previous_user = next((text for role, text in reversed(history) if role == "user"), None)
    if previous_user and (FOLLOW_RE.search(message) or _is_short_followup(message)):
        return f"{previous_user}\n{message}"
    return message
