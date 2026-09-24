from __future__ import annotations

import re

from bcra_rag.domain.freeze import freeze_footer, names_freeze
from bcra_rag.domain.guardrails.copy import NO_CLAUSE
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
    "id es el identificador de documento del extracto (A8359 o texto_ordenado), "
    "nunca un identificador de fragmento.",
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
    """Require a this-turn citation whose quote anchors, or force silencio.

    A silencio draft passes and clears citations. Otherwise each citation must
    use a document id retrieved this turn (turn_ids, not a chunk id) and
    anchor_span must find the quote. No usable citation blocks, forces
    silencio, and hides the draft. Hits are not copied in as citations.
    """

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
                detail="silencio no lleva citas",
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
                detail="hay citas de esta consulta",
                enforced=self.enforce,
                patch=RailPatch(citations=valid),
            )
        return RailResult(
            rule=self.id,
            stage=self.stage,
            verdict="block",
            detail="no hay identificador ni cita de esta consulta",
            enforced=self.enforce,
            patch=RailPatch(
                finding=Finding.SILENCIO,
                citations=[],
                answer=NO_CLAUSE,
            ),
        )


class FreezeHonestyRail:
    """Rewrite only an unqualified "vigente hoy" claim so it names the dump.

    generate_from_context still appends the dump footer when the finished
    answer does not already name the freeze. That footer is not this rail.
    """

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
                detail="la respuesta ya nombra la fecha del extracto",
                enforced=self.enforce,
            )
        if VIGENTE_CLAIM.search(ctx.answer):
            rewritten = ctx.answer.rstrip() + " " + freeze_footer(ctx.last_refresh, ctx.to_as_of)
            return RailResult(
                rule=self.id,
                stage=self.stage,
                verdict="warn",
                detail="se reescribió la respuesta para nombrar la fecha del extracto",
                enforced=self.enforce,
                patch=RailPatch(answer=rewritten),
            )
        return RailResult(
            rule=self.id,
            stage=self.stage,
            verdict="pass",
            detail="no aparece «vigente hoy» sin fecha",
            enforced=self.enforce,
        )


class PromptLeakRail:
    """Block if the answer contains the <<<DOC_…>>> fence or a system-prompt sentence.

    The fence is a random delimiter around retrieved text. This rail does not
    strip the answer.
    """

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
                detail="se filtró el delimitador",
                enforced=self.enforce,
            )
        for finger in PROMPT_FINGERPRINTS:
            if finger in blob:
                return RailResult(
                    rule=self.id,
                    stage=self.stage,
                    verdict="block",
                    detail="se filtró una instrucción interna",
                    enforced=self.enforce,
                )
        return RailResult(
            rule=self.id, stage=self.stage, verdict="pass", detail="sin filtración"
        )


class UnsafeOutputRail:
    """Redact ANSI escapes and tool-call shaped tags. Does not block."""

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
                detail="se quitaron marcas de formato o de herramientas",
                enforced=self.enforce,
                patch=RailPatch(answer=cleaned),
            )
        return RailResult(
            rule=self.id, stage=self.stage, verdict="pass", detail="limpio"
        )


class MarkdownSanitizeRail:
    """Redact HTML, javascript: and data: URLs, and Markdown images.

    A Markdown link stays only for https://bcra.gob.ar (or www). Other links
    keep the label and lose the URL. Citation snippets get the same cleanup.
    A clean answer can still patch those snippets.
    """

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
                detail="se limpió el marcado",
                enforced=self.enforce,
                patch=RailPatch(answer=cleaned, citations=citations),
            )
        return RailResult(
            rule=self.id,
            stage=self.stage,
            verdict="pass",
            detail="sin marcado",
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
    """Return (verbatim span, adjusted) or None when the quote does not anchor.

    An exact whitespace-normalized substring is kept (adjusted False). A
    verbatim run of at least 40 characters, or 60% of the quote, is returned
    in its original form with adjusted True; the rail then warns
    "cita ajustada". Anything shorter is no anchor, and cite-or-abstain
    treats that citation as unusable (silencio when none remain).
    """
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
