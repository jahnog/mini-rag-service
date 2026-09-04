from __future__ import annotations

import re

ALIAS_TABLE: tuple[tuple[str, str], ...] = (
    (r"\bMULC\b", "Mercado Único y Libre de Cambios"),
    (r"\bcepo\b", "restricciones cambiarias"),
)


def expand_aliases(text: str) -> str:
    extras: list[str] = []
    for pattern, replacement in ALIAS_TABLE:
        if re.search(pattern, text, flags=re.IGNORECASE) and replacement not in text:
            extras.append(replacement)
    if extras:
        return text + " " + " ".join(extras)
    return text
