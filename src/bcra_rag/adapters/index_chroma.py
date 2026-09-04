from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

import structlog

from bcra_rag.adapters.embeddings import resolve_embedding_function
from bcra_rag.domain.meta_filters import chroma_where, metadata_matches
from bcra_rag.domain.models import Chunk
from bcra_rag.settings import Settings

log = structlog.get_logger(__name__)

COLLECTION = "bcra_camex"


def _clean_meta(metadata: dict[str, Any]) -> dict[str, str | int | float | bool]:
    cleaned: dict[str, str | int | float | bool] = {}
    for key, value in metadata.items():
        if value is None:
            continue
        if isinstance(value, (str, int, float, bool)):
            cleaned[key] = value
        else:
            cleaned[key] = str(value)
    return cleaned


class ChromaIndex:
    def __init__(
        self,
        settings: Settings,
        *,
        embedding_function: Any | None = None,
    ) -> None:
        self._settings = settings
        self._embedding_function = embedding_function
        self._collection: Any | None = None

    def _get_collection(self) -> Any:
        if self._collection is None:
            import chromadb

            self._settings.index_dir.mkdir(parents=True, exist_ok=True)
            client = chromadb.PersistentClient(path=str(self._settings.index_dir))
            ef = resolve_embedding_function(
                self._settings, self._embedding_function
            )
            self._collection = client.get_or_create_collection(
                name=COLLECTION,
                embedding_function=ef,
            )
        return self._collection

    def upsert(self, doc_id: str, chunks: Sequence[Chunk]) -> None:
        if not chunks:
            return
        collection = self._get_collection()
        batch_size = max(1, self._settings.embedding_batch_size)
        total = len(chunks)
        for start in range(0, total, batch_size):
            piece = list(chunks[start : start + batch_size])
            ids = [chunk.chunk_id for chunk in piece]
            documents = [chunk.text for chunk in piece]
            metadatas = [
                _clean_meta({**chunk.metadata, "doc_id": doc_id}) for chunk in piece
            ]
            collection.upsert(ids=ids, documents=documents, metadatas=metadatas)
            log.info(
                "index_upsert_batch",
                doc_id=doc_id,
                done=min(start + len(piece), total),
                total=total,
            )

    def has_document(self, doc_id: str) -> bool:
        collection = self._get_collection()
        got = collection.get(where={"doc_id": doc_id}, limit=1)
        return bool(got.get("ids"))

    def delete_document(self, doc_id: str) -> None:
        collection = self._get_collection()
        if self.has_document(doc_id):
            collection.delete(where={"doc_id": doc_id})

    def search(
        self,
        query: str,
        *,
        k: int = 5,
        filters: Mapping[str, object] | None = None,
    ) -> list[Chunk]:
        collection = self._get_collection()
        count = int(collection.count() or 0)
        if count <= 0:
            return []
        n_results = max(k, 1)
        over_fetch = n_results * 3 if filters else n_results
        n_results = min(over_fetch, count)
        where = chroma_where(filters)
        kwargs: dict[str, Any] = {
            "query_texts": [query],
            "n_results": n_results,
            "include": ["documents", "metadatas", "distances"],
        }
        if where:
            kwargs["where"] = where
        try:
            raw = collection.query(**kwargs)
        except (ValueError, KeyError) as exc:
            log.warning("chroma_query_failed", error=str(exc))
            retry = {
                "query_texts": [query],
                "n_results": min(max(k, 1), count),
                "include": ["documents", "metadatas", "distances"],
            }
            try:
                raw = collection.query(**retry)
            except (ValueError, KeyError) as retry_exc:
                log.warning("chroma_query_retry_failed", error=str(retry_exc))
                return []
        ids = (raw.get("ids") or [[]])[0]
        documents = (raw.get("documents") or [[]])[0]
        metadatas = (raw.get("metadatas") or [[]])[0]
        distances = (raw.get("distances") or [[]])[0]
        hits: list[Chunk] = []
        for chunk_id, text, meta, distance in zip(
            ids, documents, metadatas, distances, strict=False
        ):
            metadata = dict(meta or {})
            if not metadata_matches(metadata, filters):
                continue
            score = 1.0 / (1.0 + float(distance or 0.0))
            metadata["score"] = score
            hits.append(Chunk(str(chunk_id), str(text), metadata))
            if len(hits) >= k:
                break
        return hits

    def get_section(self, doc_id: str, punto: str | None = None) -> str:
        collection = self._get_collection()
        docs: list[Any] = []
        if punto:
            where = {"$and": [{"doc_id": doc_id}, {"punto": punto}]}
            got = collection.get(where=where, include=["documents", "metadatas"])
            docs = got.get("documents") or []
        if not docs:
            got = collection.get(where={"doc_id": doc_id}, include=["documents", "metadatas"])
            docs = got.get("documents") or []
        joined = "\n".join(str(item) for item in docs)
        return joined[:2000]
