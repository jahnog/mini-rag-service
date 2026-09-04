from __future__ import annotations

from bcra_rag.domain.manifest import Manifest
from bcra_rag.domain.urls import TO_DOC_ID
from bcra_rag.ports.index import IndexPort
from bcra_rag.schemas import HealthResponse
from bcra_rag.settings import Settings


def dump_health(settings: Settings, index: IndexPort) -> HealthResponse:
    manifest = Manifest.load(settings.manifest_path)
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
