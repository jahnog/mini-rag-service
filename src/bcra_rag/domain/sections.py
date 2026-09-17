"""Document-order assembly of a named Comunicación section."""

from __future__ import annotations

from collections.abc import Sequence

from bcra_rag.domain.models import Chunk

_BIG = 10**6


def punto_key(value: str | None) -> tuple[int, ...]:
    if not value:
        return ()
    parts: list[int] = []
    for piece in str(value).split("."):
        parts.append(int(piece) if piece.isdigit() else _BIG)
    return tuple(parts)


def _has_ordinal(chunk: Chunk) -> bool:
    value = chunk.metadata.get("ordinal")
    return isinstance(value, int) and not isinstance(value, bool)


def order_chunks(chunks: Sequence[Chunk]) -> list[Chunk]:
    items = list(chunks)
    if items and all(_has_ordinal(c) for c in items):
        return sorted(items, key=lambda c: int(c.metadata["ordinal"]))
    indexed = list(enumerate(items))
    indexed.sort(
        key=lambda pair: (
            punto_key(str(pair[1].metadata.get("punto") or "") or None),
            pair[0],
        )
    )
    return [c for _, c in indexed]


def _matches(chunk_punto: str, punto: str) -> bool:
    return chunk_punto == punto or chunk_punto.startswith(punto + ".")


def section_text(chunks: Sequence[Chunk], punto: str | None, max_chars: int) -> str:
    ordered = order_chunks(chunks)
    pick = ordered
    if punto:
        wanted = [
            i
            for i, c in enumerate(ordered)
            if _matches(str(c.metadata.get("punto") or ""), punto)
        ]
        if wanted:
            lo = max(0, wanted[0] - 1)
            hi = min(len(ordered), wanted[-1] + 2)
            pick = ordered[lo:hi]
    return "\n".join(c.text for c in pick)[:max_chars]
