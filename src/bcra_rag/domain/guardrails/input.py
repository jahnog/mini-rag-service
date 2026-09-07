from __future__ import annotations

import re
import unicodedata

from bcra_rag.domain.guardrails.types import (
    InjectionBackend,
    RailContext,
    RailPatch,
    RailResult,
    Stage,
)

CAMEX_HINTS = re.compile(
    r"\b(bcra|camex|mulc|cepo|cambi(o|os|arias)|comunicaci[oó]n|communication|"
    r"texto ordenado|divisa|exportaci|export|importaci|liquidar|liquidate|"
    r"tipo de cambio|mercado (único|unico)|fx\b|foreign exchange|"
    r"exterior y cambios|a\s*\d{3,5}|cobro de exportaciones|proceeds|"
    r"reference rate)\b",
    re.IGNORECASE,
)
OUT_OF_SCOPE = re.compile(
    r"\b(weather|clima|wetter|madrid|f[úu]tbol|receta|banxico|banco de m[eé]xico|"
    r"netflix|python tutorial)\b",
    re.IGNORECASE,
)
FOLLOW_UP = re.compile(r"^\s*(y|and|ese|esa|eso|that|el punto)\b", re.IGNORECASE)
ADVICE_CUES = re.compile(
    r"(deber[ií]a|should i)\s+(comprar|buy|invertir|dolar)|"
    r"y si compr|"
    r"dolariz|"
    r"te recomiend|"
    r"\brecomendo\b|\brecommande\b|\braccomando\b|"
    r"devrait([- ]je)?|"
    r"deveria|"
    r"\bsollte\b|"
    r"\bsoll ich\b|"
    r"comprar d[oó]lares|buy dollars|acheter des dollars|"
    r"park (my )?pesos|"
    r"parke? (ich )?(meine )?pesos|pesos parken|"
    r"d[oó]nde (pongo|estaciono|dejo) (los )?pesos|"
    r"pr[áa]ctica de mercado|investment advice|"
    r"asesoramiento (financiero|de inversi[oó]n)",
    re.IGNORECASE,
)
DEONTIC_VETO = re.compile(
    r"deber[aá]n|no podr[aá]n|queda prohibido|"
    r"\bdeber[aá]\b|"
    r"liquidar (el )?cobro|mulc|comunicaci[oó]n\s*a|"
    r"texto ordenado|\bresidentes\b|\bexportador",
    re.IGNORECASE,
)
SECRETS = re.compile(
    r"\b((?:sk|lm|xai)-[A-Za-z0-9_-]{8,}|ghp_[A-Za-z0-9]{20,})\b"
)
_ZW = dict.fromkeys(
    map(
        ord,
        "\u200b\u200c\u200d\u2060\ufeff"
        "\u202a\u202b\u202c\u202d\u202e"
        "\u2066\u2067\u2068\u2069",
    )
)


def normalize_text(text: str) -> str:
    return unicodedata.normalize("NFKC", text).translate(_ZW)


def redact_secrets(text: str) -> str:
    return SECRETS.sub("[secret]", text)


def is_advice(text: str) -> bool:
    if not ADVICE_CUES.search(text or ""):
        return False
    if DEONTIC_VETO.search(text or ""):
        return False
    return True


class _Rail:
    def __init__(self, *, enforce: bool = True) -> None:
        self.enforce = enforce


class LengthRail(_Rail):
    id = "length"
    stage: Stage = "input"

    def __init__(self, max_chars: int, *, enforce: bool = True) -> None:
        super().__init__(enforce=enforce)
        self._max = max_chars

    def run(self, ctx: RailContext) -> RailResult:
        if len(ctx.raw) > self._max:
            return RailResult(
                rule=self.id,
                stage=self.stage,
                verdict="block",
                detail="message too long",
            )
        return RailResult(
            rule=self.id, stage=self.stage, verdict="pass", detail="within cap"
        )


class NormalizeRail(_Rail):
    id = "normalize"
    stage: Stage = "input"

    def run(self, ctx: RailContext) -> RailResult:
        folded = normalize_text(ctx.raw)
        return RailResult(
            rule=self.id,
            stage=self.stage,
            verdict="pass",
            detail="NFKC",
            patch=RailPatch(raw=folded, text=folded),
        )


class SecretsRail(_Rail):
    id = "secrets"
    stage: Stage = "input"

    def __init__(self, *, field: str = "text", enforce: bool = True) -> None:
        super().__init__(enforce=enforce)
        self._field = field
        if field == "answer":
            self.id = "secrets-output"
            self.stage = "output"

    def run(self, ctx: RailContext) -> RailResult:
        blob = ctx.answer if self._field == "answer" else ctx.text
        if SECRETS.search(blob or ""):
            return RailResult(
                rule=self.id,
                stage=self.stage,
                verdict="block",
                detail="secret_shape",
            )
        return RailResult(
            rule=self.id, stage=self.stage, verdict="pass", detail="no secrets"
        )


class NoAdviceRail(_Rail):
    id = "no-advice"
    stage: Stage = "input"

    def __init__(self, *, field: str = "text", enforce: bool = True) -> None:
        super().__init__(enforce=enforce)
        self._field = field
        if field == "answer":
            self.id = "no-advice-output"
            self.stage = "output"

    def run(self, ctx: RailContext) -> RailResult:
        blob = ctx.answer if self._field == "answer" else ctx.raw
        if not is_advice(blob or ""):
            return RailResult(
                rule=self.id, stage=self.stage, verdict="pass", detail="not advice"
            )
        if self._field == "answer" and _advice_quoted(blob, ctx):
            return RailResult(
                rule=self.id,
                stage=self.stage,
                verdict="pass",
                detail="advice quoted from this-turn hit",
            )
        return RailResult(
            rule=self.id,
            stage=self.stage,
            verdict="block",
            detail="investment advice is out of scope",
        )


class InjectionRail(_Rail):
    id = "injection"
    stage: Stage = "input"

    def __init__(self, backend: InjectionBackend, *, enforce: bool = True) -> None:
        super().__init__(enforce=enforce)
        self._backend = backend

    def run(self, ctx: RailContext) -> RailResult:
        hit, detail = self._backend.score(ctx.text)
        if hit:
            return RailResult(
                rule=self.id,
                stage=self.stage,
                verdict="block",
                detail=detail,
            )
        return RailResult(
            rule=self.id, stage=self.stage, verdict="pass", detail=detail
        )


class ScopeRail(_Rail):
    id = "scope"
    stage: Stage = "input"

    def run(self, ctx: RailContext) -> RailResult:
        latest = ctx.raw or ""
        if OUT_OF_SCOPE.search(latest):
            return RailResult(
                rule=self.id,
                stage=self.stage,
                verdict="block",
                detail="outside BCRA CAMEX / Argentine FX",
            )
        if CAMEX_HINTS.search(latest):
            return RailResult(
                rule=self.id, stage=self.stage, verdict="pass", detail="in CAMEX scope"
            )
        if FOLLOW_UP.search(latest):
            return RailResult(
                rule=self.id,
                stage=self.stage,
                verdict="pass",
                detail="in-session follow-up",
            )
        return RailResult(
            rule=self.id,
            stage=self.stage,
            verdict="block",
            detail="outside BCRA CAMEX / Argentine FX",
        )


def _advice_quoted(blob: str, ctx: RailContext) -> bool:
    match = ADVICE_CUES.search(blob or "")
    if match is None:
        return False
    span = match.group(0).lower()
    for chunk in ctx.hits:
        if span in (chunk.text or "").lower():
            return True
    for citation in ctx.citations:
        if span in (citation.snippet or "").lower():
            return True
    return False
