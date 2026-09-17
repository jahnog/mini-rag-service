from __future__ import annotations

import re

from bcra_rag.domain.freeze import freeze_footer, names_freeze
from bcra_rag.domain.guardrails.types import RailContext, RailPatch, RailResult, Stage
from bcra_rag.domain.models import Chunk
from bcra_rag.schemas import Citation, Finding

VIGENTE_CLAIM = re.compile(
    r"vigente\s+hoy|normativa vigente|current (law|rule|regulation)",
    re.IGNORECASE,
)
PROMPT_FINGERPRINTS = (
    "Respond only with JSON keys answer, finding, citations.",
    "id is a dump document id (A8359 or texto_ordenado), never a chunk id.",
    "Respondé solo con un objeto JSON con las claves answer, finding y citations.",
    "id es el id de documento del dump (A8359 o texto_ordenado), nunca un id de chunk.",
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
PUNCT_GLUE = re.compile(r"([.,:;!?])(\S)")


class CiteOrAbstainRail:
    id = "cite-or-abstain"
    stage: Stage = "output"

    def __init__(self, *, enforce: bool = True) -> None:
        self.enforce = enforce

    def run(self, ctx: RailContext) -> RailResult:
        if ctx.finding is Finding.SILENCIO:
            return RailResult(
                rule=self.id,
                stage=self.stage,
                verdict="pass",
                detail="silencio has no citations",
                enforced=self.enforce,
                patch=RailPatch(citations=[]),
            )
        allowed = ctx.turn_ids or {
            str(chunk.metadata.get("doc_id") or "") for chunk in ctx.hits
        }
        valid: list[Citation] = []
        adjusted = 0
        for citation in ctx.citations:
            if citation.id not in allowed:
                continue
            anchored = anchor_span(citation, ctx.hits)
            if anchored is None:
                continue
            span, was_adjusted = anchored
            if was_adjusted:
                adjusted += 1
                valid.append(citation.model_copy(update={"snippet": span}))
            else:
                valid.append(citation)
        if valid:
            if adjusted:
                return RailResult(
                    rule=self.id,
                    stage=self.stage,
                    verdict="warn",
                    detail=f"cita ajustada ({adjusted})",
                    enforced=self.enforce,
                    patch=RailPatch(citations=valid),
                )
            return RailResult(
                rule=self.id,
                stage=self.stage,
                verdict="pass",
                detail="citations exist in this turn",
                enforced=self.enforce,
                patch=RailPatch(citations=valid),
            )
        return RailResult(
            rule=self.id,
            stage=self.stage,
            verdict="block",
            detail="no this-turn dump id or quote",
            enforced=self.enforce,
            patch=RailPatch(
                finding=Finding.SILENCIO,
                citations=[],
                answer="No hay una cláusula citada en el dump CAMEX.",
            ),
        )


class FreezeHonestyRail:
    id = "freeze-honesty"
    stage: Stage = "output"

    def __init__(self, *, enforce: bool = True) -> None:
        self.enforce = enforce

    def run(self, ctx: RailContext) -> RailResult:
        if names_freeze(ctx.answer, ctx.last_refresh, ctx.to_as_of):
            return RailResult(
                rule=self.id,
                stage=self.stage,
                verdict="pass",
                detail="draft already names last_refresh and to_as_of",
                enforced=self.enforce,
            )
        if VIGENTE_CLAIM.search(ctx.answer):
            rewritten = ctx.answer.rstrip() + " " + freeze_footer(ctx.last_refresh, ctx.to_as_of)
            return RailResult(
                rule=self.id,
                stage=self.stage,
                verdict="warn",
                detail="rewrote answer to name last_refresh and to_as_of",
                enforced=self.enforce,
                patch=RailPatch(answer=rewritten),
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
            return RailResult(
                rule=self.id,
                stage=self.stage,
                verdict="redact",
                detail="stripped ansi or tool-shaped tags",
                enforced=self.enforce,
                patch=RailPatch(answer=cleaned),
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
        citations = [
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
                patch=RailPatch(answer=cleaned, citations=citations),
            )
        return RailResult(
            rule=self.id,
            stage=self.stage,
            verdict="pass",
            detail="no markup",
            patch=RailPatch(citations=citations),
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


MIN_ANCHOR_CHARS = 40
MIN_ANCHOR_RATIO = 0.6


def anchor_span(citation: Citation, hits: list[Chunk]) -> tuple[str, bool] | None:
    """Return (verbatim_span, adjusted) or None when the snippet has no usable anchor."""
    quote = _norm_span(citation.snippet or "")
    if not quote:
        return None
    for chunk in hits:
        if str(chunk.metadata.get("doc_id") or "") != citation.id:
            continue
        body = _norm_span(chunk.text)
        if quote in body:
            return citation.snippet, False
        run = _longest_common_run(quote, body)
        if run and (len(run) >= MIN_ANCHOR_CHARS or len(run) >= MIN_ANCHOR_RATIO * len(quote)):
            original = _recover_original(run, chunk.text)
            if original:
                return original, True
    return None


def _longest_common_run(quote: str, body: str) -> str:
    words = quote.split()
    for size in range(len(words), 2, -1):
        for start in range(0, len(words) - size + 1):
            window = " ".join(words[start : start + size])
            if window in body:
                return window
    return ""


def _recover_original(run: str, text: str) -> str:
    pattern = r"\W+".join(re.escape(word) for word in run.split())
    match = re.search(pattern, text, re.IGNORECASE)
    return match.group(0) if match else ""


def _quote_ok(citation: Citation, hits: list[Chunk]) -> bool:
    return anchor_span(citation, hits) is not None


def _norm_span(text: str) -> str:
    collapsed = WS.sub(" ", text)
    spaced = PUNCT_GLUE.sub(r"\1 \2", collapsed)
    return WS.sub(" ", spaced).strip().strip(".;:,").lower()
