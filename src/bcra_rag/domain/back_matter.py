from __future__ import annotations

import re

from bcra_rag.domain.models import Chunk

BACK_MATTER_RE = re.compile(
    r"correlaciones|historial|origen de las disposiciones|origen de las normas",
    re.IGNORECASE,
)
ASKS_BACK_MATTER_RE = re.compile(
    r"\bcorrelaciones\b|\bhistorial\b|\borigen\b",
    re.IGNORECASE,
)


def asks_for_back_matter(query: str) -> bool:
    return bool(ASKS_BACK_MATTER_RE.search(query))


def drop_back_matter(chunks: list[Chunk], query: str) -> list[Chunk]:
    if asks_for_back_matter(query):
        return chunks
    kept: list[Chunk] = []
    for chunk in chunks:
        heading = str(chunk.metadata.get("heading_path") or "")
        if BACK_MATTER_RE.search(chunk.text) or BACK_MATTER_RE.search(heading):
            continue
        kept.append(chunk)
    return kept
