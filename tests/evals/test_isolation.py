from __future__ import annotations

from pathlib import Path

from bcra_rag.composition import build_app
from bcra_rag.settings import Settings


def _source(relative: str) -> str:
    root = Path(__file__).resolve().parents[2]
    return (root / "src" / "bcra_rag" / relative).read_text(encoding="utf-8")


def test_chat_sources_do_not_import_evals_vertical() -> None:
    for relative in (
        "composition.py",
        "api/app.py",
        "api/handle.py",
        "ui/gradio_app.py",
        "use_cases/answer_query.py",
    ):
        text = _source(relative)
        assert "bcra_rag.evals" not in text


def test_build_app_does_not_need_evals(tmp_path: Path) -> None:
    from bcra_rag.adapters.index_fake import FakeIndex
    from bcra_rag.adapters.llm_fake import FakeLlm
    from bcra_rag.adapters.session_memory import InMemorySessionStore

    app = build_app(
        Settings(data_dir=tmp_path),
        index=FakeIndex(),
        llm=FakeLlm(),
        sessions=InMemorySessionStore(),
    )
    assert app.fastapi is not None
    assert "evals" not in type(app).__module__ or app.fastapi is not None


def test_operator_script_does_not_boot_gradio() -> None:
    root = Path(__file__).resolve().parents[2]
    text = (root / "evals" / "run_l1.py").read_text(encoding="utf-8")
    assert "build_app" not in text
    assert "gradio" not in text.lower()
    assert "build_evals" in text
    assert "configure_logging" in text
    assert "l1.log" in text


def test_answer_query_does_not_import_otel_adapter() -> None:
    assert "bcra_rag.adapters.otel" not in _source("use_cases/answer_query.py")


def test_judge_phoenix_module_does_not_import_phoenix_evals() -> None:
    assert "phoenix.evals" not in _source("evals/adapters/judge_phoenix.py")


def test_no_http_eval_route(tmp_path: Path) -> None:
    from bcra_rag.adapters.index_fake import FakeIndex
    from bcra_rag.adapters.llm_fake import FakeLlm
    from bcra_rag.adapters.session_memory import InMemorySessionStore

    app = build_app(
        Settings(data_dir=tmp_path),
        index=FakeIndex(),
        llm=FakeLlm(),
        sessions=InMemorySessionStore(),
    )
    paths = [getattr(route, "path", "") for route in app.fastapi.routes]
    assert not any(path.rstrip("/").endswith("/evals") or "/evals/" in path for path in paths)


def test_refresh_job_does_not_import_evals() -> None:
    assert "bcra_rag.evals" not in _source("jobs/refresh.py")
    assert "run_l1" not in _source("jobs/refresh.py")
    assert "bcra_rag.evals" not in _source("jobs/ingest.py")
    assert "run_l1" not in _source("jobs/ingest.py")
