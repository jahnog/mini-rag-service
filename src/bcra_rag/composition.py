from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache

from fastapi import FastAPI

from bcra_rag.adapters.catalog_bcra import BcraCatalog
from bcra_rag.adapters.extractor_pdftotext import PdfExtractor
from bcra_rag.adapters.index_chroma import ChromaIndex
from bcra_rag.adapters.llm_fake import UnavailableLlm
from bcra_rag.adapters.llm_openai import LlmAdapter
from bcra_rag.adapters.session_memory import InMemorySessionStore
from bcra_rag.api.routes import create_fastapi
from bcra_rag.ports.catalog import CatalogPort
from bcra_rag.ports.extractor import ExtractorPort
from bcra_rag.ports.index import IndexPort
from bcra_rag.ports.llm import LlmPort
from bcra_rag.ports.session import SessionStore
from bcra_rag.settings import Settings


@dataclass(frozen=True)
class IngestApp:
    settings: Settings
    catalog: CatalogPort
    extractor: ExtractorPort
    index: IndexPort


@dataclass(frozen=True)
class ChatApp:
    settings: Settings
    index: IndexPort
    llm: LlmPort
    sessions: SessionStore
    fastapi: FastAPI


def build_ingest(settings: Settings | None = None) -> IngestApp:
    resolved = settings or Settings()
    return IngestApp(
        settings=resolved,
        catalog=BcraCatalog(resolved),
        extractor=PdfExtractor(),
        index=ChromaIndex(resolved),
    )


def build_app(
    settings: Settings | None = None,
    *,
    index: IndexPort | None = None,
    llm: LlmPort | None = None,
    sessions: SessionStore | None = None,
) -> ChatApp:
    resolved = settings or Settings()
    resolved_index = index or ChromaIndex(resolved)
    resolved_llm = llm or (
        LlmAdapter(resolved) if resolved.llm_api_key else UnavailableLlm()
    )
    resolved_sessions = sessions or InMemorySessionStore()
    api = create_fastapi(
        settings=resolved,
        index=resolved_index,
        llm=resolved_llm,
        sessions=resolved_sessions,
    )
    return ChatApp(
        settings=resolved,
        index=resolved_index,
        llm=resolved_llm,
        sessions=resolved_sessions,
        fastapi=api,
    )


@lru_cache
def get_app() -> ChatApp:
    return build_app()

