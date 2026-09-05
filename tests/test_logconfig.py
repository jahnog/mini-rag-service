from __future__ import annotations

import json
from pathlib import Path

import pytest
import respx
import structlog

from bcra_rag.adapters.index_fake import FakeIndex
from bcra_rag.composition import IngestApp
from bcra_rag.jobs.ingest import _run as ingest_run
from bcra_rag.jobs.refresh import _run as refresh_run
from bcra_rag.logconfig import configure_logging
from bcra_rag.settings import Settings
from tests.test_ingest import A13, FakeCatalog, ScriptedExtractor, _mock_pdfs


def _last_json_line(text: str) -> dict[str, object]:
    lines = [line for line in text.splitlines() if line.strip()]
    assert lines
    data = json.loads(lines[-1])
    assert isinstance(data, dict)
    return data


def test_log_line_is_json_on_stdout_and_file(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    log_file = tmp_path / "nested" / "ingest.log"
    configure_logging(log_file=log_file)
    structlog.get_logger("bcra_rag.tests").info("probe", foo=1)
    stdout = _last_json_line(capsys.readouterr().out)
    stored = _last_json_line(log_file.read_text(encoding="utf-8"))
    for payload in (stdout, stored):
        assert payload["event"] == "probe"
        assert payload["level"] == "info"
        assert "timestamp" in payload
        assert payload["foo"] == 1


def test_omitting_log_file_does_not_create_a_file(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    configure_logging()
    structlog.get_logger("bcra_rag.tests").info("probe")
    capsys.readouterr()
    assert not (tmp_path / "logs" / "ingest.log").exists()
    assert list(tmp_path.rglob("*.log")) == []


def test_app_configures_chat_log_file() -> None:
    source = (
        Path(__file__).resolve().parents[1].joinpath("src/bcra_rag/api/app.py")
        .read_text(encoding="utf-8")
    )
    assert "configure_logging" in source
    assert "chat.log" in source
    assert "ingest.log" not in source


def _job_app(tmp_path: Path) -> IngestApp:
    settings = Settings(data_dir=tmp_path, download_concurrency=2, download_delay_s=0.0)
    return IngestApp(
        settings=settings,
        catalog=FakeCatalog([A13]),
        extractor=ScriptedExtractor(),
        index=FakeIndex(),
    )


@pytest.mark.asyncio
@respx.mock
async def test_ingest_and_refresh_jobs_write_log_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _mock_pdfs()
    app = _job_app(tmp_path)
    monkeypatch.setattr("bcra_rag.jobs.ingest.build_ingest", lambda: app)
    monkeypatch.setattr("bcra_rag.jobs.refresh.build_ingest", lambda: app)
    assert await ingest_run() == 0
    log_file = tmp_path / "logs" / "ingest.log"
    assert log_file.is_file()
    first = log_file.read_text(encoding="utf-8")
    assert "ingest_run_started" in first
    assert await refresh_run() == 0
    assert "ingest_run_started" in log_file.read_text(encoding="utf-8")
