"""Turn the model's citations into ones the page can show, and explain the ones it cannot."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Literal

from bcra_rag.domain.guardrails import RailContext
from bcra_rag.domain.guardrails.input import redact_secrets
from bcra_rag.domain.guardrails.output import _quote_ok, anchor_span
from bcra_rag.domain.models import Chunk
from bcra_rag.domain.router import named_ids
from bcra_rag.domain.urls import TO_DOC_ID, TO_PDF_URL
from bcra_rag.schemas import Citation, Finding, LlmDraft

SNIPPET_CHARS = 280


def _doc_id(chunk: Chunk) -> str:
    return str(chunk.metadata.get("doc_id") or "")


def _first_hit_by_doc(hits: list[Chunk]) -> dict[str, Chunk]:
    by_doc: dict[str, Chunk] = {}
    for chunk in hits:
        doc_id = _doc_id(chunk)
        if doc_id and doc_id not in by_doc:
            by_doc[doc_id] = chunk
    return by_doc


def citations_from_model(
    draft: LlmDraft, hits: list[Chunk], turn_ids: set[str]
) -> list[Citation]:
    """Keep citations whose id was retrieved this turn. Drop duplicate ids.

    An empty quote is filled with the first 280 characters of the first hit
    for that document. Cite-or-abstain still has to anchor it. Texto ordenado
    is forced to tipo TO.
    """
    by_doc = _first_hit_by_doc(hits)
    citations: list[Citation] = []
    seen: set[str] = set()
    for item in draft.citations:
        if item.id not in turn_ids or item.id in seen:
            continue
        seen.add(item.id)
        snippet = (item.snippet or "").strip()
        if not snippet and item.id in by_doc:
            snippet = by_doc[item.id].text[:SNIPPET_CHARS]
        tipo: Literal["A", "TO"] = "TO" if item.id == TO_DOC_ID else item.tipo
        citations.append(item.model_copy(update={"snippet": snippet, "tipo": tipo}))
    return citations


def enrich_citations(
    citations: list[Citation],
    hits: list[Chunk],
    doc_meta: Mapping[str, Mapping[str, object]],
) -> list[Citation]:
    """Fill fecha, url, and punto from the hit and the manifest.

    Whether the quote sits in the retrieved passage is anchor_span, not here.
    """
    by_doc = _first_hit_by_doc(hits)
    out: list[Citation] = []
    for item in citations:
        entry = doc_meta.get(item.id) or {}
        hit = by_doc.get(item.id)
        update: dict[str, str] = {}
        fecha = entry.get("fecha") or (hit.metadata.get("fecha") if hit is not None else None)
        url = entry.get("url") or (TO_PDF_URL if item.id == TO_DOC_ID else None)
        if fecha and not item.fecha:
            update["fecha"] = str(fecha)
        if url and not item.url:
            update["url"] = str(url)
        if not item.punto and hit is not None and hit.metadata.get("punto"):
            update["punto"] = str(hit.metadata["punto"])
        out.append(item.model_copy(update=update) if update else item)
    return out


def cite_failures(
    citations: list[Citation], turn_ids: set[str], hits: list[Chunk]
) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for item in citations:
        reason = _failure_reason(item, turn_ids, hits)
        if reason:
            snippet = redact_secrets((item.snippet or "")[:80])
            rows.append({"id": item.id, "reason": reason, "snippet": snippet})
    return rows


def _failure_reason(item: Citation, turn_ids: set[str], hits: list[Chunk]) -> str | None:
    if item.id not in turn_ids:
        return "unknown_id"
    if not (item.snippet or "").strip():
        return "empty_snippet"
    span = anchor_span(item, hits)
    if span is None:
        return "quote_not_in_hit"
    return "quote_adjusted" if span[1] else None


def _draft_names_id(answer: str, named_id: str) -> bool:
    if not named_id:
        return False
    if named_id.casefold() in (answer or "").casefold():
        return True
    return named_id in named_ids(answer)


def salvage_named(ctx: RailContext) -> str:
    """For a named-document route, repair or attach the citation to that document."""
    named = ctx.named_id or ""
    if ctx.retrieval_route != "named" or named not in ctx.turn_ids or not named:
        return "none"
    if ctx.finding is Finding.SILENCIO:
        return "none"
    hit = _first_hit_by_doc(ctx.hits).get(named)
    slice_ = (hit.text[:SNIPPET_CHARS] if hit is not None else "").strip()
    existing = next((i for i, item in enumerate(ctx.citations) if item.id == named), None)
    if existing is not None:
        return _replace_snippet(ctx, existing, slice_)
    if not ctx.citations and slice_ and _draft_names_id(ctx.answer, named):
        tipo: Literal["A", "TO"] = "TO" if named == TO_DOC_ID else "A"
        ctx.citations = [Citation(id=named, tipo=tipo, snippet=slice_)]
        return "attached_named"
    return "none"


def _replace_snippet(ctx: RailContext, index: int, slice_: str) -> str:
    citation = ctx.citations[index]
    if not slice_ or _quote_ok(citation, ctx.hits):
        return "none"
    ctx.citations[index] = citation.model_copy(update={"snippet": slice_})
    return "replaced_snippet"
