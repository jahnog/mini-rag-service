from __future__ import annotations

from bcra_rag.domain.models import Chunk
from bcra_rag.domain.urls import TO_DOC_ID
from bcra_rag.evals.domain.types import GoldRow
from bcra_rag.ports.index import IndexPort
from bcra_rag.settings import Settings


def oracle_chunks(index: IndexPort, gold: GoldRow, settings: Settings) -> list[Chunk]:
    """Load the labeled clause from the index so generation is scored without search.

    For texto ordenado, the first gold punto selects the clause. Other ids load
    the document body.
    """
    if not gold.gold_ids:
        return []
    chunks: list[Chunk] = []
    remaining = settings.max_context_chars
    for doc_id in gold.gold_ids:
        punto = gold.gold_puntos[0] if gold.gold_puntos and doc_id == TO_DOC_ID else None
        text = index.get_section(doc_id, punto)
        if not text.strip():
            continue
        clipped = text[:remaining]
        remaining -= len(clipped)
        chunks.append(
            Chunk(
                f"{doc_id}:{punto or 'body'}",
                clipped,
                {"doc_id": doc_id, "punto": punto or "", "numero": doc_id},
            )
        )
        if remaining <= 0:
            break
    return chunks


def usable_oracle(gold: GoldRow, chunks: list[Chunk]) -> bool:
    """False when the question is not answerable, gold ids are empty, or the punto is missing.

    A texto ordenado row whose gold punto did not produce a chunk with that
    punto is not usable.
    """
    if not gold.answerable or not gold.gold_ids or not chunks:
        return False
    for chunk in chunks:
        doc_id = str(chunk.metadata.get("doc_id") or "")
        if doc_id != TO_DOC_ID:
            return True
        punto = str(chunk.metadata.get("punto") or "")
        if gold.gold_puntos and punto:
            return True
    return False
