from __future__ import annotations

import re
import unicodedata

from bcra_rag.domain.guardrails.types import (
    InjectionBackend,
    RailContext,
    RailResult,
    Stage,
)

CAMEX_HINTS = re.compile(
    r"\b(bcra|camex|mulc|cepo|cambi(o|os|arias)|comunicaci[oó]n|communication|"
    r"texto ordenado|divisa|exportaci|export|importaci|liquidar|liquidate|"
    r"punto|tipo de cambio|mercado (único|unico)|fx\b|foreign exchange|"
    r"exterior y cambios|a\s*\d{3,5}|cobro de exportaciones|proceeds|"
    r"reference rate)\b",
    re.IGNORECASE,
)
OUT_OF_SCOPE = re.compile(
    r"\b(weather|clima|madrid|f[úu]tbol|receta|banxico|banco de m[eé]xico|"
    r"netflix|python tutorial)\b",
    re.IGNORECASE,
)
NO_ADVICE = re.compile(
    r"(deber[ií]a|should i|conv[ie]ene)\s+(comprar|buy|invertir)|"
    r"comprar d[oó]lares|buy dollars|park (my )?pesos|"
    r"d[oó]nde (pongo|estaciono|dejo) (los )?pesos|"
    r"pr[áa]ctica de mercado|investment advice|"
    r"asesoramiento (financiero|de inversi[oó]n)",
    re.IGNORECASE,
)
SECRETS = re.compile(r"\b(sk-[A-Za-z0-9_-]{10,}|ghp_[A-Za-z0-9]{20,})\b")
_ZW = dict.fromkeys(
    map(
        ord,
        "\u200b\u200c\u200d\u2060\ufeff"
        "\u202a\u202b\u202c\u202d\u202e"
        "\u2066\u2067\u2068\u2069",
    )
)


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
        ctx.text = unicodedata.normalize("NFKC", ctx.raw).translate(_ZW)
        ctx.raw = unicodedata.normalize("NFKC", ctx.raw).translate(_ZW)
        return RailResult(
            rule=self.id, stage=self.stage, verdict="pass", detail="NFKC"
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
        blob = ctx.answer if self._field == "answer" else ctx.text
        if NO_ADVICE.search(blob or ""):
            return RailResult(
                rule=self.id,
                stage=self.stage,
                verdict="block",
                detail="investment advice is out of scope",
            )
        return RailResult(
            rule=self.id, stage=self.stage, verdict="pass", detail="not advice"
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
        if OUT_OF_SCOPE.search(ctx.text) and not CAMEX_HINTS.search(ctx.text):
            return RailResult(
                rule=self.id,
                stage=self.stage,
                verdict="block",
                detail="outside BCRA CAMEX / Argentine FX",
            )
        if CAMEX_HINTS.search(ctx.text):
            return RailResult(
                rule=self.id, stage=self.stage, verdict="pass", detail="in CAMEX scope"
            )
        return RailResult(
            rule=self.id,
            stage=self.stage,
            verdict="block",
            detail="outside BCRA CAMEX / Argentine FX",
        )
