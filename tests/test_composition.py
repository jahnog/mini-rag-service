from pathlib import Path

from bcra_rag.composition import build_app, build_ingest


def test_build_ingest_exposes_catalog_extractor_index(
    monkeypatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    app = build_ingest()
    assert app.catalog is not None
    assert app.extractor is not None
    assert app.index is not None
    assert hasattr(app.catalog, "list_camex_a")
    assert hasattr(app.extractor, "extract_pdf")
    assert hasattr(app.index, "upsert")
    assert hasattr(app.index, "has_document")
    assert hasattr(app.index, "delete_document")


def test_build_app_exposes_extended_ports(tmp_path: Path) -> None:
    from bcra_rag.adapters.index_fake import FakeIndex
    from bcra_rag.adapters.llm_fake import FakeLlm
    from bcra_rag.adapters.session_memory import InMemorySessionStore
    from bcra_rag.settings import Settings

    app = build_app(
        Settings(data_dir=tmp_path),
        index=FakeIndex(),
        llm=FakeLlm(),
        sessions=InMemorySessionStore(),
    )
    assert hasattr(app.index, "search")
    assert hasattr(app.llm, "complete")
    assert hasattr(app.sessions, "mint")
    assert hasattr(app.sessions, "get")
    assert hasattr(app.sessions, "append")
    assert hasattr(app.sessions, "expire")
    assert hasattr(app.sessions, "clear")
    assert app.fastapi is not None
