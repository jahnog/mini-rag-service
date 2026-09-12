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
    assert "--run-live-server" in readme
    assert "-m live_server" in readme
    assert "--run-prod-smoke" in readme
    assert "-m prod_smoke" in readme
    assert "./scripts/run-prod-smoke.sh" in readme
    assert "run-prod-smoke-cron.sh" in readme
    assert "10:11" in readme
    assert "PROD_SMOKE_NOTIFY_TO" in readme
    assert "PROD_BASE_URL" in readme
    assert "PROD_PHOENIX_PROJECT_NAME" in readme
    assert "PROD_PHOENIX_COLLECTOR_ENDPOINT" in readme
    assert "playwright install chromium" in readme
    assert "tests/test_jobs_integration.py::test_ingest_command_downloads_one_real_pdf" in readme
    assert "tests/test_jobs_integration.py::test_refresh_command_downloads_one_real_pdf" in readme
    assert "--pdb" in readme
    assert "DATA_DIR/logs/ingest.log" in readme
    assert "data/logs/ingest.log" in readme
    assert "DATA_DIR/logs/chat.log" in readme
    assert "data/logs/chat.log" in readme
    assert "DATA_DIR/logs/traces.jsonl" in readme
    assert "data/logs/traces.jsonl" in readme
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
    assert "./scripts/run-l1.sh" in readme
    assert "Without ingest" in readme
    assert "Serving is down for the run" in readme
    assert "sessions do not survive" in readme
    assert "API starts again on L1 failure" in readme
    assert "banner follows the stored file" in readme
    assert "missing_extra" in readme
    assert "no cron L1" in readme
    assert "### Evals" in readme
    assert "JUDGE_MODEL" in readme
    assert "JUDGE_API_KEY" in readme
    assert "bcra_rag.evals" in readme
    assert "--deterministic-only" in readme
    assert "--retrieval-only" in readme
    assert "--generation-only" in readme
    assert "--generation-context" in readme
    assert "phoenix-evals" in readme
    assert "PHOENIX_API_KEY" in readme
    assert "CHAT_TURN_EVALS" in readme
    assert "uvicorn" in readme
    assert "unpublished" in readme.lower() or "sample" in readme.lower()
    assert "deleting `data/`" in readme
    assert "./run.sh" in readme
    assert "AGENTS.md" in readme
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


def test_run_prod_smoke_script_sets_origin_and_runs_pytest() -> None:
    text = (
        Path(__file__).resolve().parents[1] / "scripts" / "run-prod-smoke.sh"
    ).read_text(encoding="utf-8")
    assert "PROD_BASE_URL is required" in text
    assert "AUTH_PUBLIC_ORIGIN" in text
    assert "--run-prod-smoke" in text
    assert "-m prod_smoke" in text
    assert '"$@"' in text
    assert "shell=True" not in text
    assert "uvicorn" not in text
    assert "content" + "labstudy" not in text
    assert "chita" + "-ts" not in text


def test_agents_commands_list() -> None:
    agents = Path(__file__).resolve().parents[1].joinpath("AGENTS.md").read_text(
        encoding="utf-8"
    )
    assert "## Commands" in agents
    for needle in (
        "uv sync",
        "playwright install chromium",
        "./run.sh",
        "uvicorn bcra_rag.api.app:app",
        "./scripts/deploy.sh",
        "ssh -L 8000:127.0.0.1:8000",
        "systemctl start bcra-rag",
        "systemctl stop bcra-rag",
        "systemctl status bcra-rag",
        "bcra-rag-ingest",
        "bcra-rag-refresh",
        "uv run ruff check .",
        "uv run mypy src",
        "uv run pytest -q",
        "--run-integration",
        "-m integration",
        "--run-live-server",
        "-m live_server",
        "--run-prod-smoke",
        "-m prod_smoke",
        "./scripts/run-prod-smoke.sh",
        "--pdb",
        "python -m bcra_rag.jobs.ingest",
        "python -m bcra_rag.jobs.refresh",
        "evals/run_l1.py",
        "--deterministic-only",
        "--retrieval-only",
        "--generation-only",
        "--cov=src",
        "scripts/commands.toml",
        "README.md",
    ):
        assert needle in agents, needle
    assert "chita" + "-ts" not in agents
