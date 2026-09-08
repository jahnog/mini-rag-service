from pathlib import Path

import pytest

from bcra_rag.composition import build_app, build_ingest
from bcra_rag.settings import Settings


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


def test_build_evals_does_not_require_judge_extra(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from bcra_rag.adapters.index_fake import FakeIndex
    from bcra_rag.adapters.llm_fake import FakeLlm
    from bcra_rag.evals.composition import build_evals
    from bcra_rag.evals.settings import EvalSettings

    monkeypatch.setenv("LLM_API_KEY", "")
    monkeypatch.setenv("JUDGE_API_KEY", "")
    app = build_evals(
        Settings(data_dir=tmp_path),
        EvalSettings(_env_file=None, judge_api_key="", llm_api_key=""),
        index=FakeIndex(),
        llm=FakeLlm(),
    )
    assert app.judge is None
    assert app.judge_skip_reason == "no_judge"
    assert app.sink is not None
