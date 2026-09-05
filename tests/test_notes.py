from pathlib import Path

import pytest
import respx

from bcra_rag.domain.manifest import Manifest
from tests.test_ingest import A13, _mock_pdfs, _usecase


@pytest.mark.asyncio
@respx.mock
async def test_notes_mention_catalog_hole(tmp_path: Path) -> None:
    from bcra_rag.settings import Settings

    settings = Settings(data_dir=tmp_path, download_delay_s=0.0)
    _mock_pdfs()
    use_case, _, _ = _usecase(settings, [A13])
    await use_case.run("full")
    notes = settings.notes_path.read_text(encoding="utf-8")
    assert "1990" in notes
    assert "232" in notes
    assert Manifest.load(settings.manifest_path).last_refresh


def test_readme_operator_bullets() -> None:
    readme = Path(__file__).resolve().parents[1].joinpath("README.md").read_text(
        encoding="utf-8"
    )
    assert "## How to run" in readme
    assert "uv sync" in readme
    assert "uv run ruff check" in readme
    assert "uv run mypy src" in readme
    assert "uv run pytest -q" in readme
    assert "--run-integration" in readme
    assert "-m integration" in readme
    assert "tests/test_jobs_integration.py::test_ingest_command_downloads_one_real_pdf" in readme
    assert "tests/test_jobs_integration.py::test_refresh_command_downloads_one_real_pdf" in readme
    assert "--pdb" in readme
    assert "DATA_DIR/logs/ingest.log" in readme
    assert "data/logs/ingest.log" in readme
    assert "DATA_DIR/logs/chat.log" in readme
    assert "data/logs/chat.log" in readme
    assert "DATA_DIR/logs/l1.log" in readme
    assert "data/logs/l1.log" in readme
    assert "evals/l1.json" in readme
    assert "--cov-report" in readme
    assert "below 80%" in readme
    assert "poppler" in readme.lower() or "pdftotext" in readme
    assert "EMBEDDING_" in readme
    assert "EMBEDDING_BATCH_SIZE" in readme
    assert "EMBEDDING_MAX_CHARS" in readme
    assert "2048" in readme
    assert "EMBEDDING_BACKEND=onnx" in readme
    assert "LLM_API_KEY" in readme
    assert "python -m bcra_rag.jobs.ingest" in readme
    assert "python -m bcra_rag.jobs.refresh" in readme
    assert "does **not** pull new catalog ids" in readme or "does not pull new catalog" in readme
    assert "GitHub Actions cannot persist" in readme
    assert "1990" in readme
    assert "citation-id" in readme
    assert "last_refresh" in readme
    assert "evals/run_l1.py" in readme
    assert "uvicorn" in readme
    assert "unpublished" in readme.lower() or "sample" in readme.lower()
    assert "deleting `data/`" in readme
    assert "./run.sh" in readme
    assert "./scripts/deploy.sh" in readme
    assert "ssh -L 8000:127.0.0.1:8000" in readme
    assert "--ingest" in readme
    assert "systemctl start bcra-rag" in readme
    assert "systemctl stop bcra-rag" in readme
    assert "systemctl status bcra-rag" in readme
    assert "bcra-rag-ingest" in readme
    assert "bcra-rag-refresh" in readme
    assert "DEPLOY_HOST" in readme
    assert "user@dump-host" in readme
    assert "deploy/local.env" in readme
    assert "chita" + "-ts" not in readme
