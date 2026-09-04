from __future__ import annotations

from collections.abc import Mapping

from bcra_rag.domain.chunkers import FixedChunker, StructuredChunker
from bcra_rag.domain.models import Chunk


def rebuild_structured_slice(
    extracts: Mapping[str, tuple[str, dict[str, object]]],
    *,
    strategy: str,
    max_chars: int = 2048,
) -> list[Chunk]:
    """Chunk each extract with strategy A (fixed) or B (structured)."""
    chunker: FixedChunker | StructuredChunker
    if strategy == "B":
        chunker = StructuredChunker(max_chars=max_chars)
    else:
        chunker = FixedChunker(max_chars=max_chars)
    chunks: list[Chunk] = []
    for doc_id, (text, metadata) in extracts.items():
        chunks.extend(chunker.chunk(doc_id, text, dict(metadata)))
    return chunks
