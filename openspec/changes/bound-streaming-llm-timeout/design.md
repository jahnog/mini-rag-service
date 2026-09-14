## Context

See proposal.md Why and `specs/platform/spec.md`. Sibling `add-thinking` made `LlmAdapter.complete` `stream=True` so the observatory can yield thinking; HTTP `POST /chat` still waits for one `ChatResponse`. Sibling `add-prod-smoke-tests` owns `--run-prod-smoke` against `PROD_BASE_URL`. Laptop cron is 15m (`scripts/run-prod-smoke-cron.sh`).

Unchanged architecture:

- **Ports:** Catalog, Extractor, Index, Llm, SessionStore. Those five stay five. `LlmPort.complete(prompt, *, on_thinking=None) -> LlmDraft` stays the only language-model method.
- **Composition:** `build_ingest` / `build_app`; no DI container.
- **Ingest/refresh pipeline:** catalog → polite fetch → classify → extract → chunk A/B → index upsert → MANIFEST. Untouched.
- **Router / chunking / session:** aliases; named Com. A `get_section` vs vigente; one worker, `/clear`.
- **Host-side refresh:** systemd oneshots + cron.d. uvicorn remains `127.0.0.1:8000` without `--workers` or `--proxy-headers`. Reverse-proxy overlays stay operator-owned (private layout).

Constraints: Python 3.11+ (`asyncio.timeout`); default pytest and CI stay fake-only; `src` coverage >= 80%; no private hostnames in tracked files.

Today: `AsyncOpenAI(timeout=llm_timeout_s)` is an idle-between-chunks read timeout. Thinking tokens reset it. Dump-host BCRA overlay `ProxyTimeout` (180s) cuts a silent HTTP POST with HTML 502. Smoke retries 502 three times with a 30s gap into that same worker. Observatory websocket yields thinking ~every 0.12s so Apache sees activity.

## Goals / Non-Goals

**Goals:**

- Wall-clock bound on the language-model **call** (`generate_from_context` → `complete`), all adapters.
- Timeout → existing silencio / `llm_unavailable` path; never `parse_llm_draft` on a partial stream.
- Smoke: one user-like `POST /chat`; retry a **fast** 502 once; do not retry a slow proxy 502 into a busy worker.
- Document `LLM_TIMEOUT_S` vs reverse-proxy wait. Default stays 60s.

**Non-Goals:**

- HTTP SSE of the JSON answer (still slip-order item 2).
- `reasoning_effort` / extra uvicorn workers / `--proxy-headers` / worker-kill timeout.
- Committing Apache overlays or changing global `Timeout`.
- Weakening named A 3500 fail-closed.
- Changing `deploy/bcra-rag.service` ExecStart (unit tests lock it).

## Decisions

### Decision: bound at `generate_from_context`, not only in `LlmAdapter`

Wrap `await llm.complete(...)` in `asyncio.timeout(timeout_s)`. `timeout_s` is `Settings.llm_timeout_s` from `AnswerQuery._respond` and L1 `run_generation`. Keep `AsyncOpenAI(timeout=llm_timeout_s)` as the stalled-socket idle cap. Do not nest a second wall-clock inside `LlmAdapter` (60/60 noise). `TimeoutError` / cancelled `complete` fall into the existing `except Exception` → silencio, canned Spanish, empty citations, `thinking` unset, `remember=False`.

Alternative: adapter-only `wait_for` — rejected; `FakeLlm` and L1 would not be bound. Alternative: overall `/chat` middleware timeout — rejected; would 500 instead of structured silencio.

### Decision: do not parse a partial stream

On expiry, cancel the `complete` task so the assembler never returns thinking-only / truncated JSON to `parse_llm_draft`. A frequent-chunk SlowLlm (yields thinking every tens of ms past a tiny timeout) is the unit test; a single initial sleep would also trip an idle timeout and would miss the production failure.

### Decision: default stays 60s; production wait is operator

`add-thinking` already said do not change the default; operators raise `LLM_TIMEOUT_S` for long traces. Enforcing wall-clock at 60s with host still at 60 would abort observatory thinking a staff user is watching and fail smoke as 13 Sep (`llm_unavailable`). Clock order, operator-owned:

```
typical named+thinking  <  LLM_TIMEOUT_S  <  reverse-proxy wait  <  CHAT_TIMEOUT_S (480)  <  15m cron
                         host 180–240s       BCRA overlay 300s
```

Do not put hostnames or overlay paths in tracked files. README Debug and env examples state the inequality.

Alternative: raise spec default to 180 — rejected (`add-thinking`). Alternative: heartbeat/SSE on HTTP `/chat` so Apache sees bytes — slipped.

### Decision: smoke retries mimic a second click, not a stampede

`CHAT_RETRY_ATTEMPTS` today is 3 with a 30s gap. Three 300s proxy waits exceed the 15m cron. A person does not overlap three generates on one worker.

`post_chat`: retry 502/503/504 at most **once**, and only when the failed response returned in under `CHAT_FAST_FAIL_S` (~15s) — crash / connection. Gap stays `CHAT_RETRY_GAP_S` (30s covers `RestartSec=5` + import). A slow 502 (proxy wait) is the failed user turn; do not retry. `CHAT_TIMEOUT_S=480` unchanged. Named A 3500 still fails closed.

Alternative: drop all retries — worse for a 5s restart 502. Alternative: wait `LLM_TIMEOUT_S` then retry — blows 15m if the first wait was already the proxy bound.

### Decision: IBM 1–4 take/leave and slip order (unchanged)

| Take | Leave |
|---|---|
| Prompt template with last_refresh / to_as_of; structured JSON; FastAPI not Flask | Flask; model bake-off |
| RAG loop; Gradio | LlamaIndex; LangGraph agent |
| Chroma + metadata filters; upsert on refresh | Recommender |
| Vector search; parent doc = get_section; self-query ≈ regex+filters; HNSW default | FAISS second index; multi-query unless L1 citation-id is poor |

Slip: 1 deontic retry 2 HTTP SSE 3 chunking B on A-series 4 gold cap 30 5 coverage src >= 80%. Never cut: TO + post-TO ingest, resume+refresh CLI, last_refresh banner, cite-or-abstain, citation-id, unit tests, uv/ruff/mypy/pytest --cov, health HTTP 200 on empty index, polite download. Deontic scan stays slip-first in design only.

## Risks / Trade-offs

- [Host stays at `LLM_TIMEOUT_S=60` after deploy] → observatory thinking dies at 60s; smoke silencio. Raise host timeout **before or with** the API restart.
- [Host `LLM_TIMEOUT_S` > reverse-proxy wait] → HTTP 502 before silencio. Overlay wait must exceed `LLM_TIMEOUT_S`.
- [Three slow 502 retries after raising proxy] → 15m cron TIMED OUT. Fast-only single retry.
- [`CHAT_TURN_EVALS=true`] → judge after `_respond` holds the silent POST. Keep false until SSE.
- [Cancel leaks the OpenAI stream] → `asyncio.timeout` cancels `complete`; idle client timeout still caps a stalled socket.
- [Private layout leak] → env names only; `tests/test_no_private_layout.py` stays.

## Migration Plan

1. Fake-suite tests for wall-clock silencio and fast-vs-slow 502 retry (default pytest green).
2. Docs on `LLM_TIMEOUT_S` vs reverse-proxy wait. No new command fence.
3. Operator: set dump-host `LLM_TIMEOUT_S` (180–240) and BCRA overlay `ProxyTimeout` (300), confirm `CHAT_TURN_EVALS` false, then deploy / restart API.
4. Hand `./scripts/run-prod-smoke.sh` against the already-running public process. Named A 3500 must cite `A3500`.
5. Rollback: revert the wrap (idle-only timeout) and smoke retry constants; restore overlay/env. No dump wipe.

## Open Questions

None.
