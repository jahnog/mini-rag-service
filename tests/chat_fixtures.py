from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from bcra_rag.adapters.index_fake import FakeIndex
from bcra_rag.adapters.llm_fake import FakeLlm
from bcra_rag.adapters.session_memory import InMemorySessionStore
from bcra_rag.composition import build_app
from bcra_rag.domain.manifest import Manifest
from bcra_rag.domain.models import Chunk
from bcra_rag.domain.urls import TO_PDF_URL
from bcra_rag.schemas import Citation, Finding, LlmDraft
from bcra_rag.settings import Settings

LAST_REFRESH = "2026-09-01T00:00:00+00:00"
TO_AS_OF = "A8307"

IN_CORPUS_DRAFT = LlmDraft(
    answer=(
        "Los residentes deberán liquidar el cobro de exportaciones. "
        "Fuente: texto_ordenado punto 3.8.5. "
        f"last_refresh={LAST_REFRESH}; to_as_of={TO_AS_OF}."
    ),
    finding=Finding.OBLIGACION,
    citations=[
        Citation(
            id="texto_ordenado",
            tipo="TO",
            punto="3.8.5",
            snippet="Los residentes deberán liquidar el cobro de exportaciones.",
            url=TO_PDF_URL,
        )
    ],
)


def seed_ready(tmp_path: Path) -> tuple[Settings, FakeIndex, Manifest]:
    settings = Settings(data_dir=tmp_path)
    settings.dump_dir.mkdir(parents=True, exist_ok=True)
    manifest = Manifest(
        path=settings.manifest_path,
        last_refresh=LAST_REFRESH,
        to_as_of=TO_AS_OF,
        last_comm_id="A8359",
        documents={
            "texto_ordenado": {"kind": "texto_ordenado", "url": TO_PDF_URL},
            "A3500": {
                "kind": "comunicacion",
                "fecha": "2002-03-08",
                "url": "https://www.bcra.gob.ar/archivos/Pdfs/comytexord/A3500.pdf",
            },
            "A8307": {"kind": "comunicacion", "fecha": "2025-08-25"},
            "A8359": {
                "kind": "comunicacion",
                "fecha": "2025-09-01",
                "url": "https://www.bcra.gob.ar/archivos/Pdfs/comytexord/A8359.pdf",
            },
        },
    )
    manifest.save()
    index = FakeIndex()
    index.upsert(
        "texto_ordenado",
        [
            Chunk(
                "texto_ordenado:3.8.5:x",
                "Los residentes deberán liquidar el cobro de exportaciones en el MULC "
                "(Mercado Único y Libre de Cambios).",
                {
                    "doc_kind": "texto_ordenado",
                    "punto": "3.8.5",
                    "chunker": "B",
                    "fecha": "2025-08-25",
                },
            ),
            Chunk(
                "texto_ordenado:corr",
                "Correlaciones. Tabla de normas históricas.",
                {"doc_kind": "texto_ordenado", "heading_path": "Correlaciones"},
            ),
        ],
    )
    index.upsert(
        "A3500",
        [
            Chunk(
                "A3500:1",
                "Tipo de cambio de referencia. Comunicación A 3500 del año 2002.",
                {
                    "doc_kind": "comunicacion",
                    "fecha": "2002-03-08",
                    "numero": "A3500",
                    "chunker": "A",
                },
            )
        ],
    )
    index.upsert(
        "A8359",
        [
            Chunk(
                "A8359:1",
                "Adecuación del tipo de cambio de referencia posterior al texto ordenado.",
                {
                    "doc_kind": "comunicacion",
                    "fecha": "2025-09-01",
                    "numero": "A8359",
                    "chunker": "A",
                },
            )
        ],
    )
    return settings, index, manifest


def make_client(
    tmp_path: Path,
    *,
    llm: FakeLlm | None = None,
    settings: Settings | None = None,
    index: FakeIndex | None = None,
    sessions: InMemorySessionStore | None = None,
) -> tuple[TestClient, FakeLlm, FakeIndex, InMemorySessionStore]:
    seeded_settings, seeded_index, _ = seed_ready(tmp_path)
    resolved_settings = settings or seeded_settings
    resolved_index = index if index is not None else seeded_index
    resolved_llm = llm or FakeLlm(IN_CORPUS_DRAFT)
    resolved_sessions = sessions or InMemorySessionStore()
    app = build_app(
        resolved_settings,
        index=resolved_index,
        llm=resolved_llm,
        sessions=resolved_sessions,
    )
    return TestClient(app.fastapi), resolved_llm, resolved_index, resolved_sessions
