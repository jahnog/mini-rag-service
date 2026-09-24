from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Protocol

from bcra_rag.domain.models import Chunk


class IndexPort(Protocol):
    def upsert(self, doc_id: str, chunks: Sequence[Chunk]) -> None: ...

    def has_document(self, doc_id: str) -> bool: ...

    def delete_document(self, doc_id: str) -> None: ...

    def search(
        self,
        query: str,
        *,
        k: int = 5,
        filters: Mapping[str, object] | None = None,
    ) -> list[Chunk]:
        """Return the k passages the adapter chose.

        Chroma may fuse keyword and embedding rankings. This protocol only
        promises a list of chunks.
        """
        ...

    def get_section(self, doc_id: str, punto: str | None = None) -> str:
        """Load one document, or one punto, from the index.

        Used by named routing, the cross-reference hop, and the eval oracle.
        """
        ...
