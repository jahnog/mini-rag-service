# BCRA Mini-RAG

A small RAG assistant over **BCRA CAMEX** (Argentine FX regulation). Ask what a circular says; get a **cited clause** (Comunicación “A” number + punto) or honest **silencio**.

This is not a general BCRA chatbot and not legal advice. Answers are an unofficial extract of public `bcra.gob.ar` documents, dated as of the last dump refresh.

## How to run

Copy `.env.example` to `.env`. For a real index upsert set `EMBEDDING_*`. In-corpus chat needs `LLM_API_KEY` (OpenAI-compatible `LLM_*`; default base URL is `https://api.x.ai/v1`). Chat and the observatory require a session from the `bcra_rag.auth` module: set `AUTH_SECRET` (≥32 characters), `AUTH_ALLOWED_EMAILS`, and SMTP (`AUTH_SMTP_HOST`, `AUTH_SMTP_FROM`, `AUTH_SMTP_TIMEOUT_S`). `POST /chat` needs the `session` cookie issued by `POST /auth/verify`. The chat `session_id` is not portable across mailboxes. Set `AUTH_TRUST_PROXY=true` only behind a reverse proxy that overwrites `X-Forwarded-For`. `AUTH_PUBLIC_ORIGIN` should be the public `https://` origin so the session cookie is `Secure` behind TLS termination and for `/auth` POST checks. Tests inject fakes and never call a live embedding or chat API. Upserts send `EMBEDDING_BATCH_SIZE` chunks per embedding request (default 8). `EMBEDDING_MAX_CHARS` (default 2048) caps each chunk for a 1024-token host embedding server. A local `qwen3-embedding-0.6b` CPU embedding server is the intended host model; `EMBEDDING_BACKEND=onnx` uses Chroma MiniLM instead (wipe `data/index` if you switch models).

Ingest and refresh need **poppler** (`pdftotext`) on PATH.

### Setup

Install Python deps (dev group is default):

<!-- commands:setup -->
```bash
uv sync
```
<!-- /commands:setup -->

Chromium for live observatory tests (after `uv sync`): `playwright install chromium`.

Local-dev command TUI (laptop / tests only — not for the dump host). Catalog: `scripts/commands.toml`. Agent command list: `AGENTS.md`.

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

Live acceptance against an already-running local process (`LIVE_BASE_URL`, default `http://127.0.0.1:8000`). Does not spawn uvicorn. Needs IMAP (`LIVE_IMAP_*`), an allowlisted mailbox, HTTP-local `AUTH_PUBLIC_ORIGIN` matching `LIVE_BASE_URL`, and Chromium for UI scenarios. Chat/UI generation uses the process’s `LLM_*` (local llama.cpp Qwen3.6-35B-A3B or xAI grok-4.3). Default pytest skips these.

<!-- commands:test-live-server -->
```bash
uv run pytest --run-live-server -m live_server -q
```
<!-- /commands:test-live-server -->

### Debug

Drop into pdb on the first test failure. Job logs are JSON (structlog) on stdout and appended to `DATA_DIR/logs/ingest.log` (default `data/logs/ingest.log`). Chat turns append to `DATA_DIR/logs/chat.log` (default `data/logs/chat.log`). Local Qwen3.6-35B-A3B via llama.cpp uses the same `LLM_BASE_URL` / `LLM_MODEL` / dummy `LLM_API_KEY`; thinking is on by default (`LLM_ENABLE_THINKING=true`) as a provider trace (`reasoning_content` or `<think>` tags). Set `LLM_ENABLE_THINKING=false` to disable it on llama.cpp. `api.x.ai` does not receive that extra body. A longer `LLM_TIMEOUT_S` may be needed. Optional per-turn traces: set `PHOENIX_COLLECTOR_ENDPOINT=http://127.0.0.1:6006` and run a sibling Phoenix process (`uvx --from arize-phoenix phoenix serve` with `PHOENIX_HOST=127.0.0.1` and `PHOENIX_WORKING_DIR=$PWD/data/phoenix`). From another host, point `PHOENIX_COLLECTOR_ENDPOINT` at that collector URL. Install chat traces with `uv sync --extra otel`. Chat still answers if the collector is unset or down.

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

### Evals

Offline L1 is an operator command (not CI) in the `bcra_rag.evals` vertical. Chat does not load eval scoring or the judge. Calidad L1 in the UI only reads the last static file.

Copy `.env.example` to `.env`. For a published run against the dump, ingest first so the index is ready (`GET /health`). Without a ready index the CLI scores a seeded FakeIndex and writes `unpublished` / `sample`. Gold is `evals/gold.jsonl` (30 questions). A run overwrites `evals/l1.json` and appends the same published metrics to `DATA_DIR/logs/l1.log` (default `data/logs/l1.log`). Shipped `evals/l1.json` stays unpublished/sample until that operator run.

Retrieval does not call the chat model. Generation needs `LLM_API_KEY` (same OpenAI-compatible `LLM_*` as chat) and defaults to `--generation-context=oracle` (gold dump text, no search). `--generation-context=retrieved` stuffs hits from the retrieval suite in the **same** run; do not combine it with `--generation-only`. `--retrieval-only` and `--generation-only` are mutually exclusive.

Judged metrics (faithfulness, answer relevancy, context precision, context recall) need `JUDGE_API_KEY` (falls back to `LLM_API_KEY`), `JUDGE_MODEL` (default `grok-4.3`), `JUDGE_BASE_URL` (default `https://api.x.ai/v1`), `JUDGE_REASONING_EFFORT=none`, and `uv sync --extra phoenix-evals`. Without the extra or key those values are skipped with a reason, not shown as 0; hit@5, precision@5, MRR, citation-id exact, and finding exact still publish. `--deterministic-only` skips the judge even when a key is set.

Optional eval traces/annotations use the same collector as chat: `PHOENIX_COLLECTOR_ENDPOINT=http://127.0.0.1:6006` (or that collector’s URL from another host) plus `uv sync --extra otel --extra phoenix-evals`. Unset or down collector still writes `evals/l1.json`. Unit tests for the vertical live under `tests/evals` and use fakes; they never pay.

<!-- commands:evals -->
```bash
uv run python evals/run_l1.py
uv run python evals/run_l1.py --deterministic-only
uv run python evals/run_l1.py --retrieval-only
uv run python evals/run_l1.py --generation-only
```
<!-- /commands:evals -->

Headline L1 metric is **citation-id** exact (ids the model cited). Retrieval publishes hit@5 separately. Deontic retry is not in v1 (finding demotion is a deterministic post-check).

### Reports

Coverage for the package; fails if `src` coverage is below 80%. CI uses this command, not operator L1.

<!-- commands:reports -->
```bash
uv run pytest -q --cov=src --cov-report=term-missing --cov-report=xml
```
<!-- /commands:reports -->

`last_refresh` is the dump date shown on `/health` and the UI banner.

## What the product will do

- Route named `Com. A NNNN` to that document; for “vigente / hoy” questions prefer the texto ordenado plus later A’s.
- Answer in a short paragraph with `Fuente:`, citations, and a per-query guardrail log.
- Gradio UI (sibling change `bcra-mini-rag`): freeze banner, chat, citation inspector, L1 numbers.

Corpus is BCRA only. It will not fetch Banxico or other hosts.

Planning: `openspec/changes/add-ingest-scripts/` (ingest) and `openspec/changes/bcra-mini-rag/` (chat/UI).
