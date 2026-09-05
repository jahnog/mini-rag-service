from __future__ import annotations

import re
from typing import Literal
from uuid import uuid4

import structlog

from bcra_rag.domain.disclaimer import disclaimer_for
from bcra_rag.domain.finding import demote_finding
from bcra_rag.domain.guardrails import (
    V1_RULES,
    any_block,
    complete_v1_log,
    input_guardrails,
    rule_cite_or_abstain,
    rule_freeze_honesty,
)
from bcra_rag.domain.health import dump_health
from bcra_rag.domain.manifest import Manifest
from bcra_rag.domain.models import Chunk
from bcra_rag.domain.router import Router
from bcra_rag.domain.urls import TO_DOC_ID, TO_PDF_URL, constructed_pdf_url, normalize_comm_id
from bcra_rag.ports.index import IndexPort
from bcra_rag.ports.llm import LlmPort
from bcra_rag.ports.session import SessionStore
from bcra_rag.schemas import (
    ChatFilters,
    ChatRequest,
    ChatResponse,
    Citation,
    Finding,
    GuardrailVerdict,
    HitScore,
    Sidecar,
)
from bcra_rag.settings import Settings

FOLLOW_RE = re.compile(r"^\s*(y|and|ese|esa|eso|that|el punto)\b", re.IGNORECASE)
CLEAR_RE = re.compile(r"^\s*/clear\s*$", re.IGNORECASE)
log = structlog.get_logger(__name__)


class AnswerQuery:
    def __init__(
        self,
        settings: Settings,
        index: IndexPort,
        llm: LlmPort,
        sessions: SessionStore,
    ) -> None:
        self._settings = settings
        self._index = index
        self._llm = llm
        self._sessions = sessions

    async def run(self, request: ChatRequest, *, request_id: str) -> ChatResponse:
        response = await self._respond(request, request_id=request_id)
        _log_turn(request, response)
        return response

    async def _respond(self, request: ChatRequest, *, request_id: str) -> ChatResponse:
        session_id = request.session_id or self._sessions.mint()
        health = dump_health(self._settings, self._index)
        last_refresh = health.last_refresh
        to_as_of = health.to_as_of
        disclaimer = disclaimer_for(last_refresh)
        k = request.k or self._settings.default_k

        if CLEAR_RE.match(request.message or ""):
            self._sessions.clear(session_id)
            return self._silencio(
                "Sesión borrada.",
                "cleared",
                request_id=request_id,
                session_id=session_id,
                last_refresh=last_refresh,
                to_as_of=to_as_of,
                disclaimer=disclaimer,
                guardrails=_all_pass("cleared"),
            )

        if len(request.message) > self._settings.max_message_chars:
            return self._silencio(
                "El mensaje excede el máximo permitido.",
                "message_too_long",
                request_id=request_id,
                session_id=session_id,
                last_refresh=last_refresh,
                to_as_of=to_as_of,
                disclaimer=disclaimer,
                guardrails=_all_pass("message_too_long"),
            )

        guards = input_guardrails(request.message)
        if any_block(guards):
            blocked = next(item for item in guards if item.verdict == "block")
            return self._silencio(
                f"No puedo responder ({blocked.rule}).",
                blocked.rule,
                request_id=request_id,
                session_id=session_id,
                last_refresh=last_refresh,
                to_as_of=to_as_of,
                disclaimer=disclaimer,
                guardrails=complete_v1_log(
                    guards,
                    [
                        GuardrailVerdict(
                            rule="cite-or-abstain",
                            verdict="pass",
                            detail="blocked before generation",
                        ),
                        GuardrailVerdict(
                            rule="freeze-honesty",
                            verdict="pass",
                            detail="blocked before generation",
                        ),
                    ],
                ),
            )

        if not health.index_ready:
            return self._silencio(
                "El índice no está listo.",
                "index_not_ready",
                request_id=request_id,
                session_id=session_id,
                last_refresh=last_refresh,
                to_as_of=to_as_of,
                disclaimer=disclaimer,
                guardrails=complete_v1_log(guards, _output_pass()),
            )

        history = self._sessions.get(session_id)
        query = _compose_followup(request.message, history)
        manifest = Manifest.load(self._settings.manifest_path)
        routed = Router(self._index, manifest).route(
            query, k=k, to_as_of=manifest.to_as_of or to_as_of
        )
        dump_ids = set(manifest.documents)

        if routed.silencio or not routed.hits:
            reason = routed.silencio_reason or "empty_hits"
            response = self._silencio(
                "No hay una cláusula citada en el dump CAMEX.",
                reason,
                request_id=request_id,
                session_id=session_id,
                last_refresh=last_refresh,
                to_as_of=to_as_of,
                disclaimer=disclaimer,
                guardrails=complete_v1_log(guards, _output_pass()),
                sidecar=_sidecar(routed.hits, []),
            )
            self._remember(session_id, request.message, response.answer)
            return response

        prompt = _prompt(query, routed.hits, last_refresh, to_as_of)
        try:
            draft = await self._llm.complete(prompt)
        except Exception:
            return self._silencio(
                "No hay modelo disponible para completar la respuesta.",
                "llm_unavailable",
                request_id=request_id,
                session_id=session_id,
                last_refresh=last_refresh,
                to_as_of=to_as_of,
                disclaimer=disclaimer,
                guardrails=complete_v1_log(guards, _output_pass()),
            )
        citations = _citations_from_hits(routed.hits, manifest)
        if draft.citations:
            by_id = {item.id: item for item in citations}
            for item in draft.citations:
                if item.id in dump_ids and item.id in by_id:
                    by_id[item.id] = item
            citations = list(by_id.values())

        finding, citations, cite_verdict = rule_cite_or_abstain(
            draft.finding, citations, dump_ids
        )
        if request.filters is not None:
            citations = _apply_http_filters(citations, request.filters)
            if not citations:
                finding = Finding.SILENCIO
        if finding is not Finding.SILENCIO:
            cited_text = "\n".join(item.snippet for item in citations)
            finding = demote_finding(
                finding,
                cited_text,
                has_punto=any(bool(item.punto) for item in citations),
            )
        answer = draft.answer
        if finding is Finding.SILENCIO:
            answer = "No hay una cláusula citada en el dump CAMEX."
            citations = []
        answer, freeze_verdict = rule_freeze_honesty(answer, last_refresh, to_as_of)

        if citations and "Fuente:" not in answer and finding is not Finding.SILENCIO:
            answer = answer.rstrip() + f"\nFuente: {citations[0].id}"
            if citations[0].punto:
                answer += f" punto {citations[0].punto}"

        sidecar = _sidecar(routed.hits, citations)
        response = ChatResponse(
            answer=answer,
            finding=finding,
            citations=citations,
            abstain=finding is Finding.SILENCIO,
            abstain_reason="cite-or-abstain" if cite_verdict.verdict == "block" else None,
            last_refresh=last_refresh,
            to_as_of=to_as_of,
            guardrails=complete_v1_log(guards, [cite_verdict, freeze_verdict]),
            sidecar=sidecar,
            request_id=request_id,
            session_id=session_id,
            disclaimer=disclaimer,
        )
        self._remember(session_id, request.message, response.answer)
        return response

    def _remember(self, session_id: str, user: str, assistant: str) -> None:
        self._sessions.append(session_id, "user", user)
        self._sessions.append(session_id, "assistant", assistant)

    def _silencio(
        self,
        prefix: str,
        reason: str,
        *,
        request_id: str,
        session_id: str,
        last_refresh: str | None,
        to_as_of: str | None,
        disclaimer: str,
        guardrails: list[GuardrailVerdict],
        sidecar: Sidecar | None = None,
    ) -> ChatResponse:
        dated = (
            f"{prefix} last_refresh={last_refresh}; to_as_of={to_as_of}."
        )
        answer, freeze = rule_freeze_honesty(dated, last_refresh, to_as_of)
        log = complete_v1_log(guardrails, [freeze])
        if not any(item.rule == "cite-or-abstain" for item in log):
            log = complete_v1_log(
                log,
                [
                    GuardrailVerdict(
                        rule="cite-or-abstain",
                        verdict="pass",
                        detail="silencio",
                    )
                ],
            )
        return ChatResponse(
            answer=answer,
            finding=Finding.SILENCIO,
            citations=[],
            abstain=True,
            abstain_reason=reason,
            last_refresh=last_refresh,
            to_as_of=to_as_of,
            guardrails=log,
            sidecar=sidecar or Sidecar(),
            request_id=request_id,
            session_id=session_id,
            disclaimer=disclaimer,
        )


def _log_turn(request: ChatRequest, response: ChatResponse) -> None:
    log.info(
        "chat_turn",
        message=request.message,
        k=request.k,
        filters=None if request.filters is None else request.filters.model_dump(),
        **response.model_dump(),
    )


def _all_pass(detail: str) -> list[GuardrailVerdict]:
    return [
        GuardrailVerdict(rule=name, verdict="pass", detail=detail) for name in V1_RULES
    ]


def _output_pass() -> list[GuardrailVerdict]:
    return [
        GuardrailVerdict(rule="cite-or-abstain", verdict="pass", detail="silencio"),
        GuardrailVerdict(rule="freeze-honesty", verdict="pass", detail="dates named"),
    ]


def _compose_followup(message: str, history: list[tuple[str, str]]) -> str:
    if not history:
        return message
    previous_user = next((text for role, text in reversed(history) if role == "user"), None)
    if previous_user and FOLLOW_RE.search(message):
        return f"{previous_user}\n{message}"
    return message


def _prompt(
    question: str,
    hits: list[Chunk],
    last_refresh: str | None,
    to_as_of: str | None,
) -> str:
    clauses = "\n\n".join(
        f"[{chunk.metadata.get('doc_id')} punto={chunk.metadata.get('punto')}] {chunk.text[:1500]}"
        for chunk in hits
    )
    return (
        f"Dump last_refresh={last_refresh}; to_as_of={to_as_of}.\n"
        f"Question: {question}\n\n"
        f"Clauses:\n{clauses}\n\n"
        "Return JSON with answer, finding, citations. "
        "citations is an array of objects {id, tipo, punto, snippet}. "
        "Quoted clauses stay in Spanish even if the question is English. "
        "Include a Fuente: line in the answer when you cite. "
        "finding is obligacion or prohibicion only with duty verbs "
        "(deber, deberá, no podrán, queda prohibido). "
        "Name last_refresh and to_as_of in the answer. "
        "Citation id is the dump document id (A8359 or texto_ordenado), never a chunk id. "
        "tipo is TO for the texto ordenado and A for Comunicaciones A."
    )


def _citations_from_hits(hits: list[Chunk], manifest: Manifest) -> list[Citation]:
    seen: set[str] = set()
    citations: list[Citation] = []
    for chunk in hits:
        doc_id = str(chunk.metadata.get("doc_id") or "")
        if not doc_id or doc_id in seen:
            continue
        seen.add(doc_id)
        kind = str(chunk.metadata.get("doc_kind") or "")
        tipo: Literal["A", "TO"] = (
            "TO" if doc_id == TO_DOC_ID or kind == "texto_ordenado" else "A"
        )
        entry = manifest.documents.get(doc_id) or {}
        url = str(entry.get("url") or "")
        if not url:
            url = TO_PDF_URL if doc_id == TO_DOC_ID else constructed_pdf_url(doc_id)
        punto = chunk.metadata.get("punto")
        citations.append(
            Citation(
                id=doc_id,
                tipo=tipo,
                fecha=str(chunk.metadata.get("fecha") or entry.get("fecha") or "") or None,
                punto=str(punto) if punto else None,
                snippet=chunk.text[:280],
                url=url,
            )
        )
    return citations


def _apply_http_filters(citations: list[Citation], filters: ChatFilters) -> list[Citation]:
    kept: list[Citation] = []
    for citation in citations:
        if filters.tipo and citation.tipo not in filters.tipo:
            continue
        if filters.comm_id and not _comm_id_matches(citation.id, filters.comm_id):
            continue
        fecha = citation.fecha or ""
        if filters.date_from and (not fecha or fecha < filters.date_from):
            continue
        if filters.date_to and (not fecha or fecha > filters.date_to):
            continue
        kept.append(citation)
    return kept


def _comm_id_matches(citation_id: str, comm_id: str) -> bool:
    if citation_id == comm_id:
        return True
    try:
        return normalize_comm_id(citation_id) == normalize_comm_id(comm_id)
    except ValueError:
        return False


def _sidecar(hits: list[Chunk], citations: list[Citation]) -> Sidecar:
    top_k = [
        HitScore(
            id=str(chunk.metadata.get("doc_id") or chunk.chunk_id),
            score=float(chunk.metadata.get("score") or 0.0),
        )
        for chunk in hits
    ]
    retrieved = {item.id for item in top_k}
    cited = {item.id for item in citations}
    coverage = (len(cited & retrieved) / len(retrieved)) if retrieved else 0.0
    return Sidecar(
        top_k=top_k[:8],
        citation_coverage=coverage,
        grounded=bool(citations),
    )


def new_request_id() -> str:
    return str(uuid4())
