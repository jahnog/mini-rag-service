from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from bcra_rag.adapters.index_fake import FakeIndex
from bcra_rag.adapters.llm_fake import FakeLlm
from bcra_rag.adapters.session_memory import InMemorySessionStore
from bcra_rag.composition import build_app
from bcra_rag.domain.manifest import Manifest
from bcra_rag.domain.models import Chunk
from bcra_rag.settings import Settings


def _client(tmp_path: Path, index: FakeIndex | None = None) -> TestClient:
    app = build_app(
        Settings(data_dir=tmp_path, embedding_model="fake-embed"),
        index=index or FakeIndex(),
        llm=FakeLlm(),
        sessions=InMemorySessionStore(),
    )
    return TestClient(app.fastapi)


def test_health_empty_dump_is_200(tmp_path: Path) -> None:
    response = _client(tmp_path).get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["index_ready"] is False
    assert "last_refresh" in body
    assert "to_as_of" in body
    assert "last_comm_id" in body
    assert body["last_refresh"] is None
    assert body["to_as_of"] is None
    assert body["last_comm_id"] is None
    assert body["n_docs"] == 0
    assert body["embedding_model"] == "fake-embed"


def test_health_reads_ingest_manifest(tmp_path: Path) -> None:
    settings = Settings(data_dir=tmp_path)
    settings.dump_dir.mkdir(parents=True)
    manifest = Manifest(path=settings.manifest_path)
    manifest.last_refresh = "2026-09-01T00:00:00+00:00"
    manifest.to_as_of = "A8307"
    manifest.last_comm_id = "A8464"
    manifest.documents = {
        "texto_ordenado": {"kind": "texto_ordenado"},
        "A8464": {"kind": "comunicacion"},
    }
    manifest.save()
    index = FakeIndex()
    index.upsert(
        "texto_ordenado",
        [Chunk("texto_ordenado:1", "TO", {"chunker": "B"})],
    )
    body = _client(tmp_path, index).get("/health").json()
    assert body["last_refresh"] == "2026-09-01T00:00:00+00:00"
    assert body["to_as_of"] == "A8307"
    assert body["last_comm_id"] == "A8464"
    assert body["n_docs"] == 2
    assert body["index_ready"] is True


def test_jobs_modules_import() -> None:
    import bcra_rag.jobs.ingest as ingest
    import bcra_rag.jobs.refresh as refresh

    assert callable(ingest.main)
    assert callable(refresh.main)
