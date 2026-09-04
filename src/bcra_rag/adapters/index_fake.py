from __future__ import annotations

from collections.abc import Mapping, Sequence

from bcra_rag.domain.meta_filters import metadata_matches
from bcra_rag.domain.models import Chunk


class FakeIndex:
    def __init__(self) -> None:
        self.docs: dict[str, list[Chunk]] = {}
        self.upsert_calls: list[str] = []
        self.search_calls: list[tuple[str, int, Mapping[str, object] | None]] = []

    def upsert(self, doc_id: str, chunks: Sequence[Chunk]) -> None:
        stored: list[Chunk] = []
        for chunk in chunks:
            meta = {**chunk.metadata, "doc_id": doc_id}
            stored.append(Chunk(chunk.chunk_id, chunk.text, meta))
        self.docs[doc_id] = stored
        self.upsert_calls.append(doc_id)

    def has_document(self, doc_id: str) -> bool:
        return bool(self.docs.get(doc_id))

    def delete_document(self, doc_id: str) -> None:
        self.docs.pop(doc_id, None)

    def search(
        self,
        query: str,
        *,
        k: int = 5,
        filters: Mapping[str, object] | None = None,
    ) -> list[Chunk]:
        self.search_calls.append((query, k, filters))
        stop = {
            "el",
            "la",
            "los",
            "las",
            "de",
            "del",
            "y",
            "o",
            "un",
            "una",
            "en",
            "a",
            "que",
            "se",
            "es",
            "por",
            "para",
            "con",
            "the",
            "of",
            "and",
            "qué",
            "como",
            "cómo",
        }
        terms = [
            part.lower()
            for part in query.split()
            if part.strip() and part.lower() not in stop and len(part) > 2
        ]
        scored: list[tuple[float, Chunk]] = []
        for doc_id, chunks in self.docs.items():
            for chunk in chunks:
                if not metadata_matches(chunk.metadata, filters):
                    continue
                text = chunk.text.lower()
                score = 0.0
                if query.lower() and query.lower() in text:
                    score += 2.0
                score += sum(1.0 for term in terms if term in text)
                if score <= 0 and not terms:
                    score = 0.1
                if score <= 0:
                    continue
                meta = {**chunk.metadata, "score": score, "doc_id": doc_id}
                scored.append((score, Chunk(chunk.chunk_id, chunk.text, meta)))
        scored.sort(key=lambda item: item[0], reverse=True)
        return [chunk for _, chunk in scored[:k]]

    def get_section(self, doc_id: str, punto: str | None = None) -> str:
        chunks = self.docs.get(doc_id, [])
        if punto:
            for chunk in chunks:
                if str(chunk.metadata.get("punto") or "") == punto:
                    return chunk.text[:2000]
        joined = "\n".join(chunk.text for chunk in chunks)
        return joined[:2000]
