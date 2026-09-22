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
    """Chunk each extract with strategy A (fixed windows) or B (numbered clauses).

    L1 calls this on the texto ordenado extract only. The panel's A and B are
    the two chunk counts, not a quality score. This does not change the live
    index.
    """
    chunker: FixedChunker | StructuredChunker
    if strategy == "B":
        chunker = StructuredChunker(max_chars=max_chars)
    else:
        chunker = FixedChunker(max_chars=max_chars)
    chunks: list[Chunk] = []
    for doc_id, (text, metadata) in extracts.items():
        chunks.extend(chunker.chunk(doc_id, text, dict(metadata)))
    return chunks
