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
        self._floor_warned = False

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
                metadata={"hnsw:space": self._settings.index_space},
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
            except Exception as exc:
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

    def _space(self, collection: Any) -> str:
        meta = getattr(collection, "metadata", None) or {}
        return str(meta.get("hnsw:space") or "l2")

    def search(
        self,
        query: str,
        *,
        k: int = 5,
        filters: Mapping[str, object] | None = None,
    ) -> list[Chunk]:
        """Embedding search plus BM25, fused with RRF when retrieval_hybrid is on.

        An embedding is a vector for the meaning of the text; closer vectors
        are more similar. BM25 is the keyword ranking. The score floor, when
        set, can drop every hit before that fusion.
        """
        collection = self._get_collection()
        count = int(collection.count() or 0)
        if count <= 0:
            return []
        hybrid = self._settings.retrieval_hybrid
        n_results = max(k, 1)
        over_fetch = n_results * 3 if filters else n_results
        if hybrid:
            over_fetch = max(over_fetch, self._settings.retrieval_candidates)
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
        dense: list[tuple[str, str, dict[str, Any], float]] = []
        for chunk_id, text, meta, distance in zip(
            ids, documents, metadatas, distances, strict=False
        ):
            metadata = dict(meta or {})
            if not metadata_matches(metadata, filters):
                continue
            dense.append((str(chunk_id), str(text), metadata, float(distance or 0.0)))
        if not hybrid:
            hits: list[Chunk] = []
            for chunk_id, text, metadata, distance in dense:
                metadata["score"] = 1.0 / (1.0 + distance)
                hits.append(Chunk(chunk_id, text, metadata))
                if len(hits) >= k:
                    break
            return hits
        if self._below_floor(collection, dense):
            return []
        lexicon = self._lexicon(collection, count)
        lexical_ids: list[str] = []
        for chunk_id, _score in lexicon.search(query, n_results) if lexicon else []:
            row = self._lexicon_rows.get(chunk_id)
            if row is None or not metadata_matches(row[1], filters):
                continue
            lexical_ids.append(chunk_id)
        dense_by_id = {chunk_id: (text, meta, dist) for chunk_id, text, meta, dist in dense}
        fused = rrf([[item[0] for item in dense], lexical_ids])
        if not fused:
            return []
        top_score = fused[0][1]
        lexical_rank = {chunk_id: rank for rank, chunk_id in enumerate(lexical_ids, start=1)}
        hits = []
        for chunk_id, score in fused[:k]:
            if chunk_id in dense_by_id:
                text, metadata, distance = dense_by_id[chunk_id]
                metadata = dict(metadata)
                metadata["dense_score"] = 1.0 / (1.0 + distance)
            else:
                text, metadata = self._lexicon_rows[chunk_id]
                metadata = dict(metadata)
                metadata["dense_score"] = 0.0
            metadata["score"] = score / top_score if top_score else 0.0
            metadata["lexical_rank"] = lexical_rank.get(chunk_id, -1)
            hits.append(Chunk(chunk_id, text, metadata))
        return hits

    def _below_floor(
        self, collection: Any, dense: list[tuple[str, str, dict[str, Any], float]]
    ) -> bool:
        """True when retrieval_min_score is set and the best cosine hit is under it.

        The default floor is 0, which is off. Non-cosine collections ignore it.
        A true result returns no hits before BM25 fusion; the turn abstains
        with empty_hits.
        """
        floor = self._settings.retrieval_min_score
        if floor <= 0 or not dense:
            return False
        if self._space(collection) != "cosine":
            if not self._floor_warned:
                log.warning("retrieval_floor_ignored_space", space=self._space(collection))
                self._floor_warned = True
            return False
        best = 1.0 - min(item[3] for item in dense)
        if best < floor:
            log.info("retrieval_below_floor", best_similarity=round(best, 4), floor=floor)
            return True
        return False

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
