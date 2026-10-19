"""Local Chroma store of CAMEX passages (collection bcra_camex).

Upsert turns each passage into numbers and saves them. Search turns the
question into numbers the same way. The keyword index is an in-memory cache
of those stored texts, refreshed when the collection count or the manifest
time changes. It is not a second database. The nearest passages are
candidates, not yet an answer.
"""

from __future__ import annotations

import threading
from collections.abc import Mapping, Sequence
from typing import Any

import structlog

from bcra_rag.adapters.embeddings import resolve_embedding_function
from bcra_rag.domain.bm25 import Bm25Index, rrf
from bcra_rag.domain.meta_filters import chroma_where, metadata_matches
from bcra_rag.domain.models import Chunk
from bcra_rag.domain.sections import section_text
from bcra_rag.settings import Settings

log = structlog.get_logger(__name__)

COLLECTION = "bcra_camex"
# Rows asked of each ranking (embedding and BM25) before RRF keeps k.
CANDIDATES = 20


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
        self._lexicon_key: tuple[int, int] | None = None
        self._lexicon_index: Bm25Index | None = None
        self._lexicon_rows: dict[str, tuple[str, dict[str, Any]]] = {}
        self._lock = threading.Lock()

    def _get_collection(self) -> Any:
        if self._collection is None:
            import chromadb
            from chromadb.config import Settings as ChromaSettings

            self._settings.index_dir.mkdir(parents=True, exist_ok=True)
            # Embedded local client (RustBindingsAPI).
            client = chromadb.PersistentClient(
                path=str(self._settings.index_dir),
                settings=ChromaSettings(
                    chroma_api_impl="chromadb.api.rust.RustBindingsAPI",
                    anonymized_telemetry=False,
                ),
            )
            ef = resolve_embedding_function(
                self._settings, self._embedding_function
            )
            self._collection = client.get_or_create_collection(
                name=COLLECTION,
                embedding_function=ef,
                metadata={"hnsw:space": "cosine"},
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

    def _manifest_mtime_ns(self) -> int:
        try:
            return int(self._settings.manifest_path.stat().st_mtime_ns)
        except OSError:
            return 0

    def _lexicon(self, collection: Any, count: int) -> Bm25Index | None:
        key = (count, self._manifest_mtime_ns())
        with self._lock:
            if self._lexicon_index is not None and self._lexicon_key == key:
                return self._lexicon_index
            try:
                got = collection.get(include=["documents", "metadatas"])
            except Exception as exc:  # noqa: BLE001 - chroma raises many types; search falls back
                log.warning("index_lexicon_unavailable", error=str(exc))
                return None
            rows: dict[str, tuple[str, dict[str, Any]]] = {}
            docs: list[tuple[str, str]] = []
            for chunk_id, text, meta in zip(
                got.get("ids") or [],
                got.get("documents") or [],
                got.get("metadatas") or [],
                strict=False,
            ):
                rows[str(chunk_id)] = (str(text), dict(meta or {}))
                docs.append((str(chunk_id), str(text)))
            self._lexicon_index = Bm25Index.build(docs)
            self._lexicon_rows = rows
            self._lexicon_key = key
            log.info("index_lexicon_built", chunks=len(docs))
            return self._lexicon_index

    def search(
        self,
        query: str,
        *,
        k: int = 5,
        filters: Mapping[str, object] | None = None,
    ) -> list[Chunk]:
        """Embedding search plus BM25, fused with RRF.

        An embedding is a vector for the meaning of the text; closer vectors
        are more similar. BM25 is the keyword ranking. Each ranking is asked
        for at least CANDIDATES rows before RRF keeps k.
        """
        collection = self._get_collection()
        count = int(collection.count() or 0)
        if count <= 0:
            return []
        n_results = max(k, 1)
        over_fetch = max(n_results * 3 if filters else n_results, CANDIDATES)
        n_results = min(over_fetch, count)
        where = chroma_where(filters)
        kwargs: dict[str, Any] = {
            "query_texts": [query],
            "n_results": n_results,
            "include": ["documents", "metadatas"],
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
                "include": ["documents", "metadatas"],
            }
            try:
                raw = collection.query(**retry)
            except (ValueError, KeyError) as retry_exc:
                log.warning("chroma_query_retry_failed", error=str(retry_exc))
                return []
        ids = (raw.get("ids") or [[]])[0]
        documents = (raw.get("documents") or [[]])[0]
        metadatas = (raw.get("metadatas") or [[]])[0]
        dense: dict[str, tuple[str, dict[str, Any]]] = {}
        for chunk_id, text, meta in zip(ids, documents, metadatas, strict=False):
            metadata = dict(meta or {})
            if metadata_matches(metadata, filters):
                dense[str(chunk_id)] = (str(text), metadata)
        lexicon = self._lexicon(collection, count)
        lexical_ids: list[str] = []
        for chunk_id, _score in lexicon.search(query, n_results) if lexicon else []:
            row = self._lexicon_rows.get(chunk_id)
            if row is None or not metadata_matches(row[1], filters):
                continue
            lexical_ids.append(chunk_id)
        fused = rrf([list(dense), lexical_ids])
        if not fused:
            return []
        top_score = fused[0][1]
        hits: list[Chunk] = []
        for chunk_id, score in fused[:k]:
            text, metadata = dense.get(chunk_id) or self._lexicon_rows[chunk_id]
            metadata = dict(metadata)
            metadata["score"] = score / top_score if top_score else 0.0
            hits.append(Chunk(chunk_id, text, metadata))
        return hits

    def get_section(self, doc_id: str, punto: str | None = None) -> str:
        collection = self._get_collection()
        got = collection.get(where={"doc_id": doc_id}, include=["documents", "metadatas"])
        chunks = [
            Chunk(str(chunk_id), str(text), dict(meta or {}))
            for chunk_id, text, meta in zip(
                got.get("ids") or [],
                got.get("documents") or [],
                got.get("metadatas") or [],
                strict=False,
            )
        ]
        return section_text(chunks, punto, self._settings.context_chunk_chars)
