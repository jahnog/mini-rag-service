from __future__ import annotations

from bcra_rag.domain.manifest import Manifest, manifest_key
from bcra_rag.domain.urls import TO_DOC_ID
from bcra_rag.ports.index import IndexPort
from bcra_rag.schemas import HealthResponse
from bcra_rag.settings import Settings

_HEALTH_CACHE: dict[tuple[str, tuple[int, int], int], HealthResponse] = {}


def clear_health_cache() -> None:
    _HEALTH_CACHE.clear()


def dump_health(settings: Settings, index: IndexPort) -> HealthResponse:
    cache_key = (str(settings.manifest_path), manifest_key(settings.manifest_path), id(index))
    cached = _HEALTH_CACHE.get(cache_key)
    if cached is not None:
        return cached
    response = _compute_health(settings, index)
    _HEALTH_CACHE[cache_key] = response
    return response


def _compute_health(settings: Settings, index: IndexPort) -> HealthResponse:
    manifest = Manifest.load_cached(settings.manifest_path)
    n_docs = len(manifest.documents)
    index_ready = False
    if n_docs > 0:
        if TO_DOC_ID in manifest.documents:
            index_ready = index.has_document(TO_DOC_ID)
        else:
            index_ready = any(
                index.has_document(doc_id) for doc_id in manifest.documents
            )
    return HealthResponse(
        last_refresh=manifest.last_refresh,
        to_as_of=manifest.to_as_of,
        last_comm_id=manifest.last_comm_id,
        n_docs=n_docs,
        index_ready=index_ready,
        embedding_model=settings.embedding_model,
    )
