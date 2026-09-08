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


def test_build_evals_forwards_phoenix_api_key(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from bcra_rag.adapters.index_fake import FakeIndex
    from bcra_rag.adapters.llm_fake import FakeLlm
    from bcra_rag.domain.guardrails.pipeline import NoOpTracer
    from bcra_rag.evals.composition import build_evals
    from bcra_rag.evals.settings import EvalSettings

    seen: dict[str, str] = {}

    def _tracer(_settings: Settings, *, api_key: str = "") -> NoOpTracer:
        seen["api_key"] = api_key
        return NoOpTracer()

    monkeypatch.setattr("bcra_rag.evals.composition.build_tracer", _tracer)
    monkeypatch.delenv("PHOENIX_API_KEY", raising=False)
    monkeypatch.delenv("PHOENIX_COLLECTOR_ENDPOINT", raising=False)
    app = build_evals(
        Settings(data_dir=tmp_path),
        EvalSettings(_env_file=None, phoenix_api_key="pk-evals"),
        index=FakeIndex(),
        llm=FakeLlm(),
    )
    assert seen["api_key"] == "pk-evals"
    assert app.tracer is not None


def test_build_evals_skips_judge_when_find_spec_raises(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from bcra_rag.adapters.index_fake import FakeIndex
    from bcra_rag.adapters.llm_fake import FakeLlm
    from bcra_rag.evals.composition import build_evals
    from bcra_rag.evals.settings import EvalSettings

    def _boom(_name: str):
        raise ModuleNotFoundError("urllib2")

    monkeypatch.setattr("bcra_rag.evals.composition.find_spec", _boom)
    app = build_evals(
        Settings(data_dir=tmp_path),
        EvalSettings(_env_file=None, judge_api_key="secret", llm_api_key=""),
        index=FakeIndex(),
        llm=FakeLlm(),
    )
    assert app.judge is None
    assert app.judge_skip_reason == "missing_extra"


def test_build_evals_passes_api_key_to_sink(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from bcra_rag.adapters.index_fake import FakeIndex
    from bcra_rag.adapters.llm_fake import FakeLlm
    from bcra_rag.evals.adapters.sink_phoenix import PhoenixEvalSink
    from bcra_rag.evals.composition import build_evals
    from bcra_rag.evals.settings import EvalSettings

    monkeypatch.delenv("PHOENIX_API_KEY", raising=False)
    app = build_evals(
        Settings(data_dir=tmp_path),
        EvalSettings(
            _env_file=None,
            phoenix_collector_endpoint="http://127.0.0.1:6006",
            phoenix_api_key="pk-sink",
        ),
        index=FakeIndex(),
        llm=FakeLlm(),
    )
    assert isinstance(app.sink, PhoenixEvalSink)
    assert app.sink._api_key == "pk-sink"
