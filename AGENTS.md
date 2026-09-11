# AGENTS.md

Minimal operating guide for coding agents in this repo.

Human-facing How to run: `README.md`. Command catalog: `scripts/commands.toml` (TUI: `./run.sh`). Keep those three in sync when a command is added, changed, or removed.

BCRA CAMEX only. Never Banxico. Five ports, no Redis, no Next.js in v1. Default tests are fakes; `src` coverage MUST be >= 80%. Do not spawn uvicorn from tests. Do not run `--run-live-server`, `--run-prod-smoke`, or a paid L1 eval in CI.

## Commands

| Purpose | Command |
|---------|---------|
| Install deps | `uv sync` |
| Chromium for live UI tests | `uv run playwright install chromium` |
| Local-dev TUI | `./run.sh` |
| Serve API + UI | `uv run uvicorn bcra_rag.api.app:app --host 0.0.0.0 --port 8000` |
| First-time document ingest | `uv run python -m bcra_rag.jobs.ingest` |
| Document refresh | `uv run python -m bcra_rag.jobs.refresh` |
| Deploy | `DEPLOY_HOST=user@dump-host ./scripts/deploy.sh` |
| SSH UI forward | `ssh -L 8000:127.0.0.1:8000 user@dump-host` |
| Deploy and ingest | `DEPLOY_HOST=user@dump-host ./scripts/deploy.sh --ingest` |
| Start host unit | `sudo systemctl start bcra-rag` |
| Stop host unit | `sudo systemctl stop bcra-rag` |
| Status host unit | `sudo systemctl status bcra-rag` |
| Start ingest unit | `sudo systemctl start bcra-rag-ingest` |
| Start refresh unit | `sudo systemctl start bcra-rag-refresh` |
| Lint | `uv run ruff check .` |
| Types | `uv run mypy src` |
| Unit tests (fakes) | `uv run pytest -q` |
| Live BCRA PDF ingest | `uv run pytest --run-integration -m integration -q` |
| Ingest PDF smoke | `uv run pytest --run-integration tests/test_jobs_integration.py::test_ingest_command_downloads_one_real_pdf -q` |
| Refresh PDF smoke | `uv run pytest --run-integration tests/test_jobs_integration.py::test_refresh_command_downloads_one_real_pdf -q` |
| Live server tests | `uv run pytest --run-live-server -m live_server -q` |
| Production smoke | `./scripts/run-prod-smoke.sh` |
| Drop into pdb | `uv run pytest --pdb` |
| L1 eval | `uv run python evals/run_l1.py` |
| L1 deterministic | `uv run python evals/run_l1.py --deterministic-only` |
| L1 retrieval | `uv run python evals/run_l1.py --retrieval-only` |
| L1 generation | `uv run python evals/run_l1.py --generation-only` |
| Coverage (CI) | `uv run pytest -q --cov=src --cov-report=term-missing --cov-report=xml` |

Live server tests attach to an already-running process (`LIVE_BASE_URL`, default `http://127.0.0.1:8000`). They need IMAP (`LIVE_IMAP_*`), HTTP-local `AUTH_PUBLIC_ORIGIN` matching that origin, and Chromium for UI. HTTP-only: `-m live_http`.

Production smoke attaches to an already-running public origin (`PROD_BASE_URL`). `./scripts/run-prod-smoke.sh` sets `AUTH_PUBLIC_ORIGIN` from `PROD_BASE_URL` and runs `uv run pytest --run-prod-smoke -m prod_smoke -q`. It needs IMAP (`LIVE_IMAP_*`), `PROD_PHOENIX_PROJECT_NAME`, and a collector endpoint (`PROD_PHOENIX_COLLECTOR_ENDPOINT` or `PHOENIX_COLLECTOR_ENDPOINT`) that receives the public process OTLP. It does not spawn uvicorn.

## OpenSpec

Planning artifacts live under `openspec/changes/<name>/`. Apply with `/openspec-apply-change`. Do not invent extra circular families or a second UI.
