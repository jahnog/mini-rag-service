from __future__ import annotations

import re

from bcra_rag.schemas import Citation, Finding, GuardrailVerdict

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
INJECTION = re.compile(
    r"ignore (all )?(previous|prior|above) instructions|"
    r"reveal (the )?(system |hidden )?prompt|"
    r"jailbreak|you are now|olvid(a|á|e) (las |tus )?instrucciones|"
    r"mostr(a|á|ar) (el )?prompt|system prompt|hidden instructions|"
    r"ignore previous",
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
VIGENTE_CLAIM = re.compile(
    r"vigente\s+hoy|normativa vigente|current (law|rule|regulation)",
    re.IGNORECASE,
)

V1_RULES = ("no-advice", "injection", "scope", "cite-or-abstain", "freeze-honesty")


def rule_no_advice(message: str) -> GuardrailVerdict:
    if NO_ADVICE.search(message):
        return GuardrailVerdict(
            rule="no-advice",
            verdict="block",
            detail="investment advice is out of scope",
        )
    return GuardrailVerdict(rule="no-advice", verdict="pass", detail="not advice")


def rule_injection(message: str) -> GuardrailVerdict:
    if INJECTION.search(message):
        return GuardrailVerdict(
            rule="injection",
            verdict="block",
            detail="prompt injection blocked",
        )
    return GuardrailVerdict(rule="injection", verdict="pass", detail="no injection")


def rule_scope(message: str) -> GuardrailVerdict:
    if OUT_OF_SCOPE.search(message) and not CAMEX_HINTS.search(message):
        return GuardrailVerdict(
            rule="scope",
            verdict="block",
            detail="outside BCRA CAMEX / Argentine FX",
        )
    if CAMEX_HINTS.search(message):
        return GuardrailVerdict(rule="scope", verdict="pass", detail="in CAMEX scope")
    return GuardrailVerdict(
        rule="scope",
        verdict="block",
        detail="outside BCRA CAMEX / Argentine FX",
    )


def input_guardrails(message: str) -> list[GuardrailVerdict]:
    return [rule_no_advice(message), rule_injection(message), rule_scope(message)]


def any_block(verdicts: list[GuardrailVerdict]) -> bool:
    return any(item.verdict == "block" for item in verdicts)


def rule_cite_or_abstain(
    finding: Finding,
    citations: list[Citation],
    dump_ids: set[str],
) -> tuple[Finding, list[Citation], GuardrailVerdict]:
    if finding is Finding.SILENCIO:
        return (
            finding,
            [],
            GuardrailVerdict(
                rule="cite-or-abstain",
                verdict="pass",
                detail="silencio has no citations",
            ),
        )
    valid = [c for c in citations if c.id in dump_ids]
    if valid:
        return (
            finding,
            valid,
            GuardrailVerdict(
                rule="cite-or-abstain",
                verdict="pass",
                detail="citations exist in the dump",
            ),
        )
    return (
        Finding.SILENCIO,
        [],
        GuardrailVerdict(
            rule="cite-or-abstain",
            verdict="block",
            detail="no dump document id; forced silencio",
        ),
    )


def rule_freeze_honesty(
    answer: str,
    last_refresh: str | None,
    to_as_of: str | None,
) -> tuple[str, GuardrailVerdict]:
    refresh = last_refresh or "desconocido"
    as_of = to_as_of or "desconocido"
    has_refresh = refresh in answer
    has_as_of = as_of in answer
    if has_refresh and has_as_of:
        return answer, GuardrailVerdict(
            rule="freeze-honesty",
            verdict="pass",
            detail="draft already names last_refresh and to_as_of",
        )
    if VIGENTE_CLAIM.search(answer):
        rewritten = (
            answer.rstrip() + f" (last_refresh={refresh}; to_as_of={as_of})"
        )
        return rewritten, GuardrailVerdict(
            rule="freeze-honesty",
            verdict="warn",
            detail="rewrote answer to name last_refresh and to_as_of",
        )
    return answer, GuardrailVerdict(
        rule="freeze-honesty",
        verdict="pass",
        detail="no unqualified vigente claim",
    )


def complete_v1_log(
    existing: list[GuardrailVerdict],
    extra: list[GuardrailVerdict],
) -> list[GuardrailVerdict]:
    by_rule = {item.rule: item for item in existing}
    for item in extra:
        by_rule[item.rule] = item
    return [by_rule[name] for name in V1_RULES if name in by_rule]
