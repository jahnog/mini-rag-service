from __future__ import annotations

import re

from bcra_rag.domain.guardrails.types import RailContext, RailResult, Stage
from bcra_rag.domain.models import Chunk
from bcra_rag.schemas import Citation, Finding

VIGENTE_CLAIM = re.compile(
    r"vigente\s+hoy|normativa vigente|current (law|rule|regulation)",
    re.IGNORECASE,
)
PROMPT_FINGERPRINTS = (
    "Respond only with JSON keys answer, finding, citations.",
    "id is a dump document id (A8359 or texto_ordenado), never a chunk id.",
)
ANSI = re.compile(r"\x1b\[[0-9;]*[A-Za-z]")
TOOL_SHAPE = re.compile(
    r"(?is)<tool_call\b|function_call\s*\(|<\|im_start\|>|<\|im_end\|>"
)
HTML_TAG = re.compile(r"(?is)<[^>]+>")
BAD_SCHEME = re.compile(r"(?i)(javascript|data)\s*:")
MD_IMAGE = re.compile(r"!\[[^\]]*]\([^)]+\)")
MD_LINK = re.compile(r"\[([^\]]+)]\(([^)]+)\)")
BCRA_HTTPS = re.compile(r"^https://(www\.)?bcra\.gob\.ar/", re.IGNORECASE)
WS = re.compile(r"\s+")


class CiteOrAbstainRail:
    id = "cite-or-abstain"
    stage: Stage = "output"

    def __init__(self, *, enforce: bool = True) -> None:
        self.enforce = enforce

    def run(self, ctx: RailContext) -> RailResult:
        if ctx.finding is Finding.SILENCIO:
            ctx.citations = []
            return RailResult(
                rule=self.id,
                stage=self.stage,
                verdict="pass",
                detail="silencio has no citations",
                enforced=self.enforce,
            )
        allowed = ctx.turn_ids or {
            str(chunk.metadata.get("doc_id") or "") for chunk in ctx.hits
        }
        valid: list[Citation] = []
        for citation in ctx.citations:
            if citation.id not in allowed:
                continue
            if _quote_ok(citation, ctx.hits):
                valid.append(citation)
        if valid:
            ctx.citations = valid
            return RailResult(
                rule=self.id,
                stage=self.stage,
                verdict="pass",
                detail="citations exist in this turn",
                enforced=self.enforce,
            )
        ctx.finding = Finding.SILENCIO
        ctx.citations = []
        ctx.answer = "No hay una cláusula citada en el dump CAMEX."
        return RailResult(
            rule=self.id,
            stage=self.stage,
            verdict="block",
            detail="no this-turn dump id or quote",
            enforced=self.enforce,
        )


class FreezeHonestyRail:
    id = "freeze-honesty"
    stage: Stage = "output"

    def __init__(self, *, enforce: bool = True) -> None:
        self.enforce = enforce

    def run(self, ctx: RailContext) -> RailResult:
        refresh = ctx.last_refresh or "desconocido"
        as_of = ctx.to_as_of or "desconocido"
        has_refresh = refresh in ctx.answer
        has_as_of = as_of in ctx.answer
        if has_refresh and has_as_of:
            return RailResult(
                rule=self.id,
                stage=self.stage,
                verdict="pass",
                detail="draft already names last_refresh and to_as_of",
                enforced=self.enforce,
            )
        if VIGENTE_CLAIM.search(ctx.answer):
            ctx.answer = ctx.answer.rstrip() + f" (last_refresh={refresh}; to_as_of={as_of})"
            return RailResult(
                rule=self.id,
                stage=self.stage,
                verdict="warn",
                detail="rewrote answer to name last_refresh and to_as_of",
                enforced=self.enforce,
            )
        return RailResult(
            rule=self.id,
            stage=self.stage,
            verdict="pass",
            detail="no unqualified vigente claim",
            enforced=self.enforce,
        )


class PromptLeakRail:
    id = "prompt-leak"
    stage: Stage = "output"

    def __init__(self, *, enforce: bool = True) -> None:
        self.enforce = enforce

    def run(self, ctx: RailContext) -> RailResult:
        blob = ctx.answer or ""
        if ctx.delimiter and ctx.delimiter in blob:
            return RailResult(
                rule=self.id,
                stage=self.stage,
                verdict="block",
                detail="delimiter leaked",
                enforced=self.enforce,
            )
        for finger in PROMPT_FINGERPRINTS:
            if finger in blob:
                return RailResult(
                    rule=self.id,
                    stage=self.stage,
                    verdict="block",
                    detail="system prompt fingerprint",
                    enforced=self.enforce,
                )
        return RailResult(
            rule=self.id, stage=self.stage, verdict="pass", detail="no leak"
        )


class UnsafeOutputRail:
    id = "unsafe-output"
    stage: Stage = "output"

    def __init__(self, *, enforce: bool = True) -> None:
        self.enforce = enforce

    def run(self, ctx: RailContext) -> RailResult:
        original = ctx.answer
        cleaned = ANSI.sub("", original)
        cleaned = TOOL_SHAPE.sub("", cleaned)
        if cleaned != original:
            ctx.answer = cleaned
            return RailResult(
                rule=self.id,
                stage=self.stage,
                verdict="redact",
                detail="stripped ansi or tool-shaped tags",
                enforced=self.enforce,
            )
        return RailResult(
            rule=self.id, stage=self.stage, verdict="pass", detail="clean"
        )


class MarkdownSanitizeRail:
    id = "markdown-sanitize"
    stage: Stage = "output"

    def __init__(self, *, enforce: bool = True) -> None:
        self.enforce = enforce

    def run(self, ctx: RailContext) -> RailResult:
        original = ctx.answer
        cleaned = _sanitize_markup(original)
        ctx.answer = cleaned
        ctx.citations = [
            citation.model_copy(update={"snippet": _sanitize_markup(citation.snippet)})
            for citation in ctx.citations
        ]
        if cleaned != original:
            return RailResult(
                rule=self.id,
                stage=self.stage,
                verdict="redact",
                detail="sanitized markup",
                enforced=self.enforce,
            )
        return RailResult(
            rule=self.id, stage=self.stage, verdict="pass", detail="no markup"
        )


def _sanitize_markup(text: str) -> str:
    out = HTML_TAG.sub("", text)
    out = BAD_SCHEME.sub("", out)
    out = MD_IMAGE.sub("", out)

    def _link(match: re.Match[str]) -> str:
        label, url = match.group(1), match.group(2).strip()
        if BCRA_HTTPS.match(url):
            return match.group(0)
        return label

    return MD_LINK.sub(_link, out)


def _quote_ok(citation: Citation, hits: list[Chunk]) -> bool:
    quote = _norm_span(citation.snippet or "")
    if not quote:
        return True
    for chunk in hits:
        if str(chunk.metadata.get("doc_id") or "") != citation.id:
            continue
        body = _norm_span(chunk.text)
        if quote in body:
            return True
        snippet = _norm_span(chunk.text[:280])
        if quote in snippet or snippet in quote:
            return True
    return False


def _norm_span(text: str) -> str:
    return WS.sub(" ", text).strip().strip(".;:,").lower()
