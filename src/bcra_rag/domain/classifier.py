from __future__ import annotations

import re
from enum import StrEnum

from bcra_rag.domain.urls import normalize_comm_id

REPRINT_RE = re.compile(
    r"actualizaci[oó]n del texto ordenado|hojas? de reemplazo|replacement sheets",
    re.IGNORECASE,
)
ADECUACION_RE = re.compile(r"adecuaci[oó]n", re.IGNORECASE)

_TO_AS_OF_PATTERNS = (
    re.compile(
        r"comunicaci[oó]n\s*[\"“']?A[\"”']?\s*(\d{3,5})[^\n]{0,80}incorporad",
        re.IGNORECASE,
    ),
    re.compile(
        r"incorporad[^\n]{0,80}comunicaci[oó]n\s*[\"“']?A[\"”']?\s*(\d{3,5})",
        re.IGNORECASE,
    ),
    re.compile(
        r"[uú]ltima comunicaci[oó]n incorporada[:\s]*A\s*(\d{3,5})",
        re.IGNORECASE,
    ),
)


class DocKind(StrEnum):
    """comunicacion is a full circular. texto_ordenado is the consolidated text.

    event is a reprint title: actualización del texto ordenado, hojas de
    reemplazo, or replacement sheets.
    """

    FULL = "comunicacion"
    EVENT = "event"
    TEXTO_ORDENADO = "texto_ordenado"


def classify_title(title: str, *, is_texto_ordenado: bool = False) -> DocKind:
    """Pick DocKind from the catalog title.

    is_adecuacion is a separate title check and does not pick the chunker.
    """
    if is_texto_ordenado:
        return DocKind.TEXTO_ORDENADO
    if REPRINT_RE.search(title):
        return DocKind.EVENT
    return DocKind.FULL


def is_adecuacion(title: str) -> bool:
    return ADECUACION_RE.search(title) is not None


def parse_to_as_of(text: str) -> str | None:
    """Comunicación named as incorporated in the first 4000 characters.

    That value is the freeze's to_as_of. It is not a search result.
    """
    header = text[:4000]
    for pattern in _TO_AS_OF_PATTERNS:
        match = pattern.search(header)
        if match:
            return normalize_comm_id(match.group(1))
    return None
