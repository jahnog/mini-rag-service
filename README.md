# BCRA Mini-RAG

A small retrieval-augmented assistant over **BCRA CAMEX**, the Argentine central bank's foreign-exchange regulation. Ask what a circular says and get a **cited clause** (Comunicación “A” number plus *punto*), or an explicit **silencio** when the corpus has no answer.

This is not a general BCRA chatbot and not legal advice. Answers are an unofficial extract of public `bcra.gob.ar` documents, dated as of the last corpus refresh.

## What it does

- Routes a named `Com. A NNNN` question to that document; for “vigente / hoy” questions it prefers the texto ordenado plus later Comunicaciones A.
- Answers in a short paragraph with a `Fuente:` line, citations, and a per-query guardrail log.
- Fuses dense and BM25 lexical retrieval over a local Chroma index.
- Serves a Gradio UI on the same FastAPI process: corpus-date freeze banner, chat, citation inspector, and the last L1 eval numbers.
- Gates chat behind email one-time-code sessions with per-mailbox and per-process daily turn caps.

The corpus is BCRA only; the ingest jobs never fetch from other hosts.

## How to run

Copy `.env.example` to `.env`. The main configuration groups:

- **Embeddings** (`EMBEDDING_*`): required for a real index upsert. Upserts send `EMBEDDING_BATCH_SIZE` chunks per request (default 8); `EMBEDDING_MAX_CHARS` (default 2048) caps each chunk for a 1024-token embedding server. The intended host model is a local `qwen3-embedding-0.6b` CPU server behind `EMBEDDING_BASE_URL`; `EMBEDDING_BACKEND=onnx` uses Chroma's built-in MiniLM instead. Wipe `data/index` when you switch embedding models.
- **Chat model** (`LLM_*`): any OpenAI-compatible endpoint. `LLM_API_KEY` is required for chat; the default base URL is `https://api.x.ai/v1`. A local llama.cpp server works with the same `LLM_BASE_URL` / `LLM_MODEL` and a dummy key.
- **Auth** (`AUTH_*`, module `bcra_rag.auth`): chat and the observatory need a session. Set `AUTH_SECRET` (at least 32 characters), `AUTH_ALLOWED_EMAILS` (`*` for any well-formed mailbox; empty sends nothing), and SMTP (`AUTH_SMTP_HOST`, `AUTH_SMTP_FROM`, `AUTH_SMTP_TIMEOUT_S`). `POST /chat` needs the `session` cookie issued by `POST /auth/verify` or the emailed login link; sessions last `AUTH_SESSION_DAYS` (default 1), and a chat `session_id` is not portable across mailboxes. Set `AUTH_PUBLIC_ORIGIN` to the public `https://` origin so the cookie is `Secure` behind TLS termination, `/auth` POST origin checks pass, and login links point at the right host. Set `AUTH_TRUST_PROXY=true` only behind a reverse proxy that overwrites `X-Forwarded-For`.
- **Quotas**: authenticated chat is capped at `CHAT_TURNS_PER_EMAIL_DAY` (default 30) and `CHAT_TURNS_PER_PROCESS_DAY` (default 100).

Tests inject fakes and never call a live embedding or chat API. Ingest and refresh need **poppler** (`pdftotext`) on `PATH`.

### Setup

Install Python deps (the dev group is included by default):

<!-- commands:setup -->
```bash
uv sync
```
<!-- /commands:setup -->

Chromium for the live UI tests (after `uv sync`): `uv run playwright install chromium`.

A command picker for local development (not for the deploy host). Its catalog is `scripts/commands.toml`; the agent-facing command list is `AGENTS.md`.

```bash
./run.sh
```

### Build

There is no compile or image-build step.

### Run

API and Gradio UI on one FastAPI process, single worker. Open http://127.0.0.1:8000/ for the UI; `GET /health` and `POST /chat` are served by the same process.

<!-- commands:run -->
```bash
uv run uvicorn bcra_rag.api.app:app --host 0.0.0.0 --port 8000
```
<!-- /commands:run -->

### Deploy

Installs over SSH to the *dump host*: the server that holds the downloaded corpus and the Chroma index. Set `DEPLOY_HOST` (required) and optionally `DEPLOY_USER` and `DEPLOY_DIR`, or copy `deploy/local.env.example` to the gitignored `deploy/local.env`. The systemd units are templates (`__DEPLOY_USER__` / `__DEPLOY_DIR__`) that `./scripts/deploy.sh` renders on the host; do not copy the unit files into systemd by hand.

First deploy:

<!-- commands:deploy -->
```bash
DEPLOY_HOST=user@dump-host ./scripts/deploy.sh
```
<!-- /commands:deploy -->

Then fill in the remote `LLM_API_KEY` and `EMBEDDING_*` (point `EMBEDDING_BASE_URL` at your OpenAI-compatible embedding server) and re-run `./scripts/deploy.sh`. Updates use the same command; it does not wipe `data/` or `.env`.

The API binds to loopback on the host (127.0.0.1:8000). Forward it to your machine:

<!-- commands:ssh-forward -->
```bash
ssh -L 8000:127.0.0.1:8000 user@dump-host
```
<!-- /commands:ssh-forward -->

One-time ingest (the embedding server at `EMBEDDING_BASE_URL` must be reachable from the host):

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

There is no cron L1 and no L1 systemd unit; the dump-host L1 run is on demand via `./scripts/run-l1.sh` (see Evals).

### Test

Lint, types, and unit tests. Default pytest uses fakes and needs no live BCRA, embedding, or chat API. CI runs these plus the coverage command under Reports.

<!-- commands:test-unit -->
```bash
uv run ruff check .
uv run mypy src
uv run pytest -q
```
<!-- /commands:test-unit -->

Live ingest/refresh tests download one real texto ordenado PDF each. They need poppler and network access; default pytest skips them.

<!-- commands:test-integration -->
```bash
uv run pytest --run-integration -m integration -q
uv run pytest --run-integration tests/test_jobs_integration.py::test_ingest_command_downloads_one_real_pdf -q
uv run pytest --run-integration tests/test_jobs_integration.py::test_refresh_command_downloads_one_real_pdf -q
```
<!-- /commands:test-integration -->

Live acceptance tests attach to an already-running local process (`LIVE_BASE_URL`, default `http://127.0.0.1:8000`); they do not spawn uvicorn. They need IMAP access to an allowlisted mailbox (`LIVE_IMAP_*`, `LIVE_EMAIL`), an HTTP-local `AUTH_PUBLIC_ORIGIN` matching `LIVE_BASE_URL`, and Chromium for the UI scenarios. Chat and UI generation use whatever `LLM_*` the process is configured with. `-m live_http` runs the HTTP-only subset. Default pytest skips these.

<!-- commands:test-live-server -->
```bash
uv run pytest --run-live-server -m live_server -q
```
<!-- /commands:test-live-server -->

Production HTTP smoke attaches to an already-running public origin (`PROD_BASE_URL`). `./scripts/run-prod-smoke.sh` exports `AUTH_PUBLIC_ORIGIN` from `PROD_BASE_URL` and runs `uv run pytest --run-prod-smoke -m prod_smoke -q`; it does not spawn uvicorn. It needs IMAP (`LIVE_IMAP_*`), `PROD_PHOENIX_PROJECT_NAME`, and a collector endpoint (`PROD_PHOENIX_COLLECTOR_ENDPOINT`, falling back to `PHOENIX_COLLECTOR_ENDPOINT`) that receives the public process's OTLP traces — not a local development Phoenix. Chat generation uses the process's `LLM_*`. Default pytest skips these.

`scripts/run-prod-smoke-cron.sh` wraps that run for a daily cron on an operator machine; the shipped `scripts/prod-smoke.crontab` schedules it at 10:11 local time. When the run finishes it emails `PROD_SMOKE_NOTIFY_TO` (falling back to `LIVE_EMAIL`) via `AUTH_SMTP_*` with OK, FAILED, or TIMED OUT. It is not a dump-host timer and not CI.

<!-- commands:test-prod-smoke -->
```bash
./scripts/run-prod-smoke.sh
```
<!-- /commands:test-prod-smoke -->

### Debug

Drop into pdb on the first test failure:

<!-- commands:debug -->
```bash
uv run pytest --pdb
```
<!-- /commands:debug -->

**Logs.** Job logs are JSON (structlog) on stdout and appended to `DATA_DIR/logs/ingest.log` (default `data/logs/ingest.log`). Chat turns append to `DATA_DIR/logs/chat.log` (default `data/logs/chat.log`). Compact per-span records append to `DATA_DIR/logs/traces.jsonl` (default `data/logs/traces.jsonl`) whether or not a collector is configured; a write failure never fails a chat turn. Each `chat_turn` line logs `retrieve_ms`, `llm_ms`, `ttft_ms`, and `thinking_chars`.

**Thinking and generation.** A local llama.cpp server (for example Qwen3.6-35B-A3B) uses the same `LLM_BASE_URL` / `LLM_MODEL` and a dummy `LLM_API_KEY`. With a llama.cpp backend, thinking is on by default (`LLM_ENABLE_THINKING=true`) and arrives as a provider trace (`reasoning_content` or `<think>` tags); set `LLM_ENABLE_THINKING=false` to disable it. `api.x.ai` never receives that extra body. Controls: `LLM_TEMPERATURE` (0.1), `LLM_MAX_TOKENS` (1500; with thinking on, llama.cpp counts reasoning tokens inside this bound, so raise it or set `LLM_REASONING_BUDGET`), `LLM_SEED` (unset), `LLM_REASONING_BUDGET` (0 = provider default; llama.cpp only), `LLM_THINKING_USER_LAYOUT` (false: Usuario turns run without thinking). A timed-out call becomes `abstain_reason=llm_timeout`; an unreadable body retries once without thinking, then yields `llm_bad_json`.

**Timeouts.** `LLM_TIMEOUT_S` is wall-clock for the whole language-model call, including a streamed thinking trace (default 60). It must be below the reverse-proxy wait; a thinking-on named Com. A question often needs more than 60. If a host overlay raises it to 600, the production-smoke HTTP client wait (`CHAT_TIMEOUT_S`) must be above that. `POST /chat` writes JSON-whitespace keepalives so a reverse proxy keeps seeing bytes while the call is in progress (the observatory websocket already streams thinking).

**Retrieval.** `CONTEXT_CHUNK_CHARS` (3000) caps each prompt chunk and a fetched named section; re-ingest once to add chunk ordinals (older indexes fall back to punto order). Retrieval fuses dense and BM25 lexical hits (`RETRIEVAL_HYBRID`, true; `RETRIEVAL_CANDIDATES`, 20 per side). `RETRIEVAL_MIN_SCORE` (0 = off) turns a best cosine similarity under the floor into a silencio with `empty_hits`; it only applies to cosine collections. `INDEX_SPACE` (cosine) applies to a new collection only — to switch an existing index, stop the service, delete `data/index`, and re-ingest.

**Traces (Phoenix).** Optional per-turn traces: set `PHOENIX_COLLECTOR_ENDPOINT=http://127.0.0.1:6006` (process environment or the project `.env`) and run a sibling Phoenix process (`uvx --from arize-phoenix phoenix serve` with `PHOENIX_HOST=127.0.0.1` and `PHOENIX_WORKING_DIR=$PWD/data/phoenix`). From another host, point `PHOENIX_COLLECTOR_ENDPOINT` at that collector's URL; set `PHOENIX_API_KEY` when the collector requires auth (a local `uvx` serve needs none). Install the tracing extra with `uv sync --extra otel`; it includes the Phoenix REST client so an L1 run can attach `retrieval.*` / `generation.*` scores. Chat still answers if the collector is unset or down. Each turn is one `chat.turn` tree (guardrails, retrieve, generate); LLM usage is stored on it as `metadata.prompt_tokens` / `metadata.completion_tokens` when the provider sends it (`stream_options.include_usage`). The tracer posts OTLP to `/v1/traces` even if the env URL is only the Phoenix host. Pytest never reads the `.env` collector URL.

**Page views (Matomo).** Optional observatory page-view tracking: set `MATOMO_URL` (an `https` tracker origin ending in `/`) and `MATOMO_SITE_ID`. Unset or invalid values send nothing; loopback hosts skip the tracker unless `?matomo=1`. The tracker is cookieless, honours Do Not Track, and never sends the mailbox or the question text.

**Per-turn evals.** `CHAT_TURN_EVALS=true` plus `JUDGE_API_KEY` (falls back to `LLM_API_KEY`) scores faithfulness and answer relevancy after each turn with two extra judge calls. Default off; do not enable it against a local llama.cpp unless you accept the latency. Scores land as Phoenix span attributes (`eval.faithfulness`, `eval.answer_relevancy`) and a `chat_turn_eval` log line, not in the chat HTTP body.

### Ingest data

The one-time ingest loads the official CAMEX tipo-A catalog (Com. A 13 / 1981 → present) plus the current texto ordenado *Exterior y Cambios*. Refresh appends new Comunicaciones A and replaces the texto ordenado only when its checksum changed. Both jobs run on the machine that holds the corpus and index; GitHub Actions cannot persist the Chroma index.

<!-- commands:ingest -->
```bash
uv run python -m bcra_rag.jobs.ingest
uv run python -m bcra_rag.jobs.refresh
```
<!-- /commands:ingest -->

A second `jobs.ingest` after a successful run does **not** pull new catalog ids; use refresh. Wipe and rebuild by deleting `data/`.

The ingest notes file records the 1990–97 gap in tagged CAMEX Comunicaciones A (sequence 232→314). Untagged A ids in that range are not crawled just to close the jump.

### Evals

Offline L1 is an operator command (not CI) in the `bcra_rag.evals` vertical. Chat never loads eval scoring or the judge; the *Calidad L1* panel in the UI only reads the last stored result.

**Local run.** With `.env` in place, ingest first so the index is ready (`GET /health`). Without ingest the CLI scores a seeded `FakeIndex` and writes an `unpublished` / `sample` result — not corpus quality. Gold is `evals/gold.jsonl` (50 questions). A run overwrites `evals/l1.json` and appends the same published metrics to `DATA_DIR/logs/l1.log` (default `data/logs/l1.log`). The committed `evals/l1.json` is the last operator run on the published corpus (published together with the corpus by `scripts/publish-data.sh`); a fresh host is seeded with it and then keeps its own runs. `ndcg_at_5` in the committed file predates the NDCG bound fix and can exceed 1 until the next operator run.

**Dump host.** After ingest on that host, run `DEPLOY_HOST=user@dump-host ./scripts/run-l1.sh` (same suite flags as the local CLI). Serving is down for the run; in-process sessions do not survive. The API starts again on L1 failure so the Calidad L1 panel reloads the stored document. The unpublished/sample banner follows the stored file, not where the run was launched from. `GET /l1` returns the document the running process serves. After changing prompts, retrieval, or citation anchoring, rerun L1 on the dump host; `finding_exact`, `citation_snippet_grounded`, and generation latency are expected to move.

Retrieval does not call the chat model. Generation needs `LLM_API_KEY` (the same OpenAI-compatible `LLM_*` as chat) and defaults to `--generation-context=oracle` (gold corpus text, no search). `--generation-context=retrieved` uses hits from the retrieval suite in the **same** run; do not combine it with `--generation-only`. `--retrieval-only` and `--generation-only` are mutually exclusive.

Judged metrics (faithfulness, answer relevancy, context precision, context recall) need `JUDGE_API_KEY` (falls back to `LLM_API_KEY`), `JUDGE_MODEL` (default `grok-4.3`), `JUDGE_BASE_URL` (default `https://api.x.ai/v1`), `JUDGE_REASONING_EFFORT=none`, and `uv sync --extra phoenix-evals`. Without the extra (`skip_reason` `missing_extra`) or the key, those values are skipped with a reason rather than shown as 0; hit@5, precision@5, MRR, citation-id exact, and finding exact still publish. `--deterministic-only` skips the judge even when a key is set. The dump-host helper does not install the judged extra.

Optional eval traces and annotations use the same collector as chat (`PHOENIX_COLLECTOR_ENDPOINT`, `PHOENIX_API_KEY`) plus `uv sync --extra otel --extra phoenix-evals`; an unset or down collector still writes `evals/l1.json`. Unit tests for the vertical live under `tests/evals`, use fakes, and never call a paid API. `--gate` compares the published metrics with the floors in `evals/gate.toml` and exits non-zero on a regression (a skipped suite fails unless `--gate-allow-skipped`); update the floors when you publish a new `evals/l1.json`.

<!-- commands:evals -->
```bash
uv run python evals/run_l1.py
uv run python evals/run_l1.py --deterministic-only
uv run python evals/run_l1.py --retrieval-only
uv run python evals/run_l1.py --generation-only
uv run python evals/run_l1.py --gate
DEPLOY_HOST=user@dump-host ./scripts/run-l1.sh
```
<!-- /commands:evals -->

The headline L1 metric is **citation-id** exact match (the ids the model cited). Retrieval publishes hit@5 separately. Finding demotion is a deterministic post-check, not a model retry.

### Reports

Coverage for the package; the run fails if `src` coverage is below 80%. CI runs this command, not the operator L1.

<!-- commands:reports -->
```bash
uv run pytest -q --cov=src --cov-report=term-missing --cov-report=xml
```
<!-- /commands:reports -->

`last_refresh` is the corpus date shown on `/health` and in the UI banner.

## Project layout

`src/bcra_rag/` follows a ports-and-adapters layout: `domain/` (routing, chunking, BM25, guardrails), `ports/` (catalog, extractor, index, LLM, session protocols), `adapters/` (BCRA catalog client, `pdftotext`, Chroma, OpenAI-compatible LLM), `use_cases/`, `api/`, `ui/` (Gradio), `auth/`, `jobs/` (ingest, refresh), and `evals/`. `composition.py` wires them together.

## Planning

Design and task history lives under `openspec/changes/` (active) and `openspec/changes/archive/` (completed). The original ingest and chat/UI proposals are `openspec/changes/archive/2026-09-02-add-ingest-scripts/` and `openspec/changes/archive/2026-09-02-bcra-mini-rag/`.
