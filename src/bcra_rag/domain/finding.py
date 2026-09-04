from __future__ import annotations

import re

from bcra_rag.schemas import Finding

DUTY_RE = re.compile(
    r"\bdeber([aáe]|án|ánse)?\b|\bdeben\b|\bno podr[aá]n\b|queda prohibido|"
    r"\bprohibid[oa]s?\b|\best[aá] prohibido\b",
    re.IGNORECASE,
)
NUMBERED_DUTY_RE = re.compile(
    r"\d+(?:\.\d+)*\.?\s+\S.{0,80}(deber|no podr|prohibid)",
    re.IGNORECASE,
)


def snippet_has_duty(text: str) -> bool:
    return bool(DUTY_RE.search(text) or NUMBERED_DUTY_RE.search(text))


def demote_finding(
    finding: Finding, snippets: str, *, has_punto: bool = False
) -> Finding:
    if finding not in {Finding.OBLIGACION, Finding.PROHIBICION}:
        return finding
    if snippet_has_duty(snippets):
        return finding
    if finding is Finding.OBLIGACION and has_punto:
        return Finding.PROCEDIMIENTO
    return Finding.DEFINICION
