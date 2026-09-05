# BCRA Mini-RAG

A small RAG assistant over **BCRA CAMEX** (Argentine FX regulation). Ask what a circular says; get a **cited clause** (Comunicación “A” number + punto) or honest **silencio**.

This is not a general BCRA chatbot and not legal advice. Answers are an unofficial extract of public `bcra.gob.ar` documents, dated as of the last dump refresh.

## How to run

Copy `.env.example` to `.env`. For a real index upsert set `EMBEDDING_*`. In-corpus chat needs `LLM_API_KEY` (OpenAI-compatible `LLM_*`; default base URL is `https://api.x.ai/v1`). Tests inject fakes and never call a live embedding or chat API. Upserts send `EMBEDDING_BATCH_SIZE` chunks per embedding request (default 8). `EMBEDDING_MAX_CHARS` (default 2048) caps each chunk for a 1024-token host embedding server. A local `qwen3-embedding-0.6b` CPU embedding server is the intended host model; `EMBEDDING_BACKEND=onnx` uses Chroma MiniLM instead (wipe `data/index` if you switch models).

Ingest and refresh need **poppler** (`pdftotext`) on PATH.

### Setup

Install Python deps (dev group is default):

<!-- commands:setup -->
```bash
uv sync
```
<!-- /commands:setup -->

Local-dev command TUI (laptop / tests only — not for the dump host). Catalog: `scripts/commands.toml`.

```bash
./run.sh
```

### Build

There is no compile or image-build step.

### Run

API + Gradio on FastAPI, one worker. Open http://127.0.0.1:8000/ for the UI; `GET /health` and `POST /chat` on the same process.

<!-- commands:run -->
```bash
uv run uvicorn bcra_rag.api.app:app --host 0.0.0.0 --port 8000
```
<!-- /commands:run -->

### Deploy

SSH install to a dump host. Set `DEPLOY_HOST` (required), optionally `DEPLOY_USER` and `DEPLOY_DIR`, or copy `deploy/local.env.example` to gitignored `deploy/local.env`. Units are templates (`__DEPLOY_USER__` / `__DEPLOY_DIR__`); `./scripts/deploy.sh` renders them on the host — do not `cp` the unit files into systemd by hand.

First deploy:

<!-- commands:deploy -->
```bash
DEPLOY_HOST=user@dump-host ./scripts/deploy.sh
```
<!-- /commands:deploy -->

Fill remote `LLM_API_KEY` and `EMBEDDING_*` (point `EMBEDDING_BASE_URL` at your OpenAI-compatible embedding server) and re-run `./scripts/deploy.sh`. Update is the same command; it does not wipe `data/` or `.env`.

SSH local-forward to the loopback UI (API binds 127.0.0.1:8000):

<!-- commands:ssh-forward -->
```bash
ssh -L 8000:127.0.0.1:8000 user@dump-host
```
<!-- /commands:ssh-forward -->

One-time ingest (the embedding server at `EMBEDDING_BASE_URL` must be up):

<!-- commands:deploy-ingest -->
```bash
DEPLOY_HOST=user@dump-host ./scripts/deploy.sh --ingest
```
<!-- /commands:deploy-ingest -->

On the host:

<!-- commands:systemctl -->
```bash
sudo systemctl start bcra-rag
sudo systemctl stop bcra-rag
sudo systemctl status bcra-rag
sudo systemctl start bcra-rag-ingest
sudo systemctl start bcra-rag-refresh
```
<!-- /commands:systemctl -->

### Test

Ruff, mypy, and `pytest -q`. Default pytest has no live BCRA or embedding API. CI pytest is the Reports coverage command.

<!-- commands:test-unit -->
```bash
uv run ruff check .
uv run mypy src
uv run pytest -q
```
<!-- /commands:test-unit -->

Live ingest/refresh (one real texto ordenado PDF each; needs poppler and network). Default pytest skips these.

<!-- commands:test-integration -->
```bash
uv run pytest --run-integration -m integration -q
uv run pytest --run-integration tests/test_jobs_integration.py::test_ingest_command_downloads_one_real_pdf -q
uv run pytest --run-integration tests/test_jobs_integration.py::test_refresh_command_downloads_one_real_pdf -q
```
<!-- /commands:test-integration -->

### Debug

Drop into pdb on the first test failure. Job logs are JSON (structlog) on stdout and appended to `DATA_DIR/logs/ingest.log` (default `data/logs/ingest.log`). Chat turns append to `DATA_DIR/logs/chat.log` (default `data/logs/chat.log`). An L1 operator run still overwrites `evals/l1.json` and appends the same published metrics to `DATA_DIR/logs/l1.log` (default `data/logs/l1.log`).

<!-- commands:debug -->
```bash
uv run pytest --pdb
```
<!-- /commands:debug -->

### Ingest data

One-time ingest loads the official CAMEX tipo-A catalog (Com. A 13 / 1981 → present) plus the current texto ordenado *Exterior y Cambios*. Refresh appends new A’s and replaces the TO only when its checksum changed. Both jobs run on the machine that holds the dump. GitHub Actions cannot persist the Chroma index.

<!-- commands:ingest -->
```bash
uv run python -m bcra_rag.jobs.ingest
uv run python -m bcra_rag.jobs.refresh
```
<!-- /commands:ingest -->

A second `jobs.ingest` after a successful run does **not** pull new catalog ids; use refresh. Wipe and rebuild by deleting `data/`.

The dump note records the 1990–97 CAMEX tag hole (sequence 232→314). Untagged A ids from that range are not crawled solely to close the jump.

### Reports

Coverage for the package; fails if `src` coverage is below 80%. Offline L1 is an operator command (not CI). Shipped `evals/l1.json` is unpublished/sample until an operator run. Deontic retry is not in v1 (finding demotion is a deterministic post-check).

<!-- commands:reports -->
```bash
uv run pytest -q --cov=src --cov-report=term-missing --cov-report=xml
uv run python evals/run_l1.py
```
<!-- /commands:reports -->

Headline L1 metric is **citation-id** exact. `last_refresh` is the dump date shown on `/health` and the UI banner.

## What the product will do

- Route named `Com. A NNNN` to that document; for “vigente / hoy” questions prefer the texto ordenado plus later A’s.
- Answer in a short paragraph with `Fuente:`, citations, and a per-query guardrail log.
- Gradio UI (sibling change `bcra-mini-rag`): freeze banner, chat, citation inspector, L1 numbers.

Corpus is BCRA only. It will not fetch Banxico or other hosts.

Planning: `openspec/changes/add-ingest-scripts/` (ingest) and `openspec/changes/bcra-mini-rag/` (chat/UI).
