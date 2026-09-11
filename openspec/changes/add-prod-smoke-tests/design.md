## Context

See proposal.md Why and the delta specs under `specs/prod-smoke/` and `specs/platform/`.

Product runtime already exists. Unchanged architecture (restated so this design satisfies the constitution):

- **Ports:** Catalog, Extractor, Index (owns embeddings), Llm, SessionStore. This change does **not** add a port. IMAP and collector REST stay test-only; `bcra_rag.auth` still sends with `SmtpMailer` only; chat still fail-opens on collector errors.
- **Composition:** `build_ingest` / `build_app`; no DI container. Prod smoke does not call `build_app`. It speaks HTTP to the operator’s already-running process at `PROD_BASE_URL`.
- **Ingest/refresh pipeline:** catalog → polite fetch → classify → extract → chunk A/B → index upsert → MANIFEST checkpoint. Untouched.
- **Router / chunking / session:** aliases; named Com. A `get_section` vs vigente (TO ∪ later A’s); serving uses structured chunker B on TO + clean A’s and fixed A otherwise; in-process session (last six messages), one worker, `/clear`. Chat memory stays bound to the authenticated email.
- **Host-side refresh:** systemd oneshots + cron.d on the dump host (not GitHub Actions). Untouched. This change does **not** add a dump-host timer or a GitHub Actions schedule.

Constraints: Python 3.11+ via uv; pytest already in the dev group; FastAPI + Gradio mounted at `/`; no private hostnames in tracked files (`tests/test_no_private_layout.py`); default pytest and CI stay fake-only; `src` coverage >= 80% on the fake suite.

Today: `tests/features/live/` is HTTP-local Gherkin (`LIVE_BASE_URL` default loopback, leftover OTP reuse, Playwright). Laptop `.env` typically has `AUTH_PUBLIC_ORIGIN` and `PHOENIX_PROJECT_NAME` aimed at that local process / `bcra-rag-dev`. Chat traces use `phoenix.otel.register(..., batch=True)`; nothing in `src` calls `tracer.flush()`.

## Goals / Non-Goals

**Goals:**

- Opt-in plain pytest against the running public origin: health, typed OTP, login-link confirm, A 3500 citation, weather silencio, collector `chat.turn` poll.
- Distinct env (`PROD_BASE_URL`, `PROD_PHOENIX_PROJECT_NAME`) so a local live `.env` cannot silently target loopback or the dev collector project.
- Reuse IMAP helpers and httpx; unit-test parse/poll with `FakeMailbox` / `respx`.
- Keep default `uv run pytest -q` and GitHub Actions fake-only.

**Non-Goals:**

- Spawning uvicorn; Playwright; Gherkin (avoid pytest-bdd phrase collisions).
- IMAP inside `bcra_rag.auth`; a sixth port; Redis.
- Leftover UNSEEN OTP reuse; allowlist-miss; logout; injection/no-advice; A 9999; `/clear`.
- Product `flush()`; SSH `chat.log`; GitHub schedule; dump-host timer.
- Naming the public hostname or mailbox in tracked files.
- The PyPI package named `phoenix`.
- CI live mail, language-model calls, or a collector.

## Decisions

### Decision: attach to the public origin, do not spawn

`PROD_BASE_URL` is **required** when `--run-prod-smoke` is set (no loopback default). Session start:

1. Origin-match `AUTH_PUBLIC_ORIGIN` to `PROD_BASE_URL` (scheme+host+port). Mismatch → `UsageError` naming both, before IMAP.
2. `GET {PROD_BASE_URL}/health` (timeout a few seconds). Connect failure → **fail**. No `subprocess.Popen(uvicorn)`.
3. `LIVE_IMAP_*` required (same as live). Missing → **fail**.
4. `PROD_PHOENIX_PROJECT_NAME` required, plus `PROD_PHOENIX_COLLECTOR_ENDPOINT` or `PHOENIX_COLLECTOR_ENDPOINT`. Missing → **fail**. Do **not** fall back to `PHOENIX_PROJECT_NAME` (local `.env` is often `bcra-rag-dev`).

`DEMO_API_KEY` unset, or sent as `x-demo-key`. HTTP 429 from the 20/60s limiter is fail-fast, not skip. Sequential only.

HTTPS: `cookie_secure` is true; httpx stores `Secure` cookies on https URLs. Assert `HttpOnly` and, when the origin scheme is https, `Secure`.

Alternatives: reuse `LIVE_BASE_URL` (rejected: laptop `.env` points at loopback); spawn uvicorn (not the public process).

### Decision: `--run-prod-smoke` is not `--run-live-server`

Extend `tests/conftest.py` with a third independent skip loop. Never return early from `pytest_collection_modifyitems`. Marker `prod_smoke` in `pyproject.toml`.

Without the flag, skip `prod_smoke`. The live and integration flags do not unskip it. `pytest --run-prod-smoke -m prod_smoke` does not run live Gherkin or catalog downloads.

Plain pytest under `tests/prod/` (not pytest-bdd). Default collection still imports the module; skip before any network.

Command (README + `scripts/commands.toml` `confirm = true`, TUI `ALLOWED_RUNNABLE`):

```bash
uv run pytest --run-prod-smoke -m prod_smoke -q
```

Document that the pytest process must set `AUTH_PUBLIC_ORIGIN` to the same origin as `PROD_BASE_URL`. CI `test.yml` unchanged.

### Decision: two real sends; no leftover reuse

`max_sends_per_email_minute` is 1. OTP consume burns the login token and vice versa.

Reuse `tests/features/live/mailbox.py`. Add `parse_login_url` (`/auth/link/[A-Za-z0-9_-]+` from plaintext; labeled OTP regex already ignores the URL). Unit-test with `FakeMailbox`. Prod smoke waits for a **new** UID ≥ request time (~45s poll). Coalesce with no new mail is a **fail**.

Session-scoped fixtures in **one** module (`tests/prod/test_smoke.py`) encode that DAG. Tests only assert; they MUST NOT re-send mail or re-post chat. Do not rely on pytest collection order across files.

1. `prod_health` — `GET /health`; fail if not HTTP 200 or `index_ready` is false.
2. `prod_otp_session` — client A `POST /auth/request` + new IMAP + `POST /auth/verify`; yields client A, email, `Set-Cookie`, `send1_at`.
3. `prod_chats` — depends on `prod_otp_session`; record `t0`; client A posts A 3500 then weather; yields both response bodies.
4. `prod_traces` — depends on `prod_chats`; poll collector using `t0` and both question texts (≤90s). Overlaps the 60s send gap in wall-clock with chat; login-link does not depend on this fixture.
5. `prod_link_session` — depends on `prod_otp_session` (`send1_at`). Waits `remaining_send_gap_s` itself. Client A (already authenticated) `POST /auth/request` for send 2 + new IMAP. **Cookie-less client B** (empty jar, never called `/auth/request`) wash `GET /auth/link/{token}` with `follow_redirects=False` → `GET /auth/link` (confirm HTML names the mailbox) → `POST /auth/link` with `Origin`/`Referer` = public origin (no `Sec-Fetch-Mode: navigate`) → `GET /auth/me`. Replay of that mail’s 6-digit code on another client must not authenticate.

Client B is the mail-click path (no `auth_intent`). Requesting send 2 from B would set intent on B and would not match the spec.

`make_client` in the live helper follows redirects; prod wash MUST pass `follow_redirects=False` on the token GET so `auth_link` is set before confirm POST.

Alternatives: one send that only asserts the URL is present (does not prove consume); same client requests and consumes (same-browser confirm, not mail-click); Playwright click (out of scope); split files whose test order is the DAG (rejected).

### Decision: A 3500 fails closed; weather is the irrelevant probe

Live Gherkin skips A 3500 on `index_ready` false / `llm_unavailable` / `missing_document`. Prod smoke **fails** those: an unread dump or a down model is the outage the operator is checking.

Question text: `Qué dice la Comunicación A 3500?` (same as live). Require a citation id `A3500`. Weather: `What's the weather in Madrid?` → finding `silencio`, scope `block` (no LLM). Structured contract fields still present on both.

Health `index_ready` false at session start → fail (do not skip into chat).

### Decision: collector REST with httpx, not MCP and not `phoenix.client`

Chat export is OTLP `/v1/traces` with `batch=True` and no `flush()`. Spans appear after the BatchSpanProcessor interval. Poll ~1s, bound ~90s.

Helper (test-only):

- Strip `/v1/traces` the same way `_collector_host` does. Host is `PROD_PHOENIX_COLLECTOR_ENDPOINT` when set, else `PHOENIX_COLLECTOR_ENDPOINT`.
- `GET {host}/v1/projects/{PROD_PHOENIX_PROJECT_NAME}/spans?name=chat.turn&start_time={t0}&limit=100` and follow `next_cursor`.
- `Authorization: Bearer {PHOENIX_API_KEY}` when the key is non-empty and not an unexpanded `${…}` placeholder.
- Match `attributes["input.value"]` (or nested `attributes.input.value`) containing the question (redacted/truncated to 500 chars in product; these questions are safe).
- Then `GET .../spans?trace_id={id}` and require a `retrieve` child on the A 3500 trace and a `scope` child on the weather trace.
- Timeout names host, project, and whether the project returned any `chat.turn` (zero spans means the public process is not exporting to that collector/project).

Default pytest: `respx` fake. Do not import `phoenix.client` or `phoenix.otel` on that path. Do not add the PyPI package named `phoenix`.

MCP `getSpans` / `listProjectTraces` is the same REST; operators MAY use MCP to inspect a failure. The test process does not speak MCP.

Alternatives: `phoenix.client` (extra `otel` / `phoenix-evals`, not in default `uv sync`); product `flush()` (rejected; this change is tests-only).

### Decision: IBM 1–4 take/leave (unchanged)

| Take | Leave |
|---|---|
| Prompt template with last_refresh / to_as_of; structured JSON; FastAPI not Flask | Flask; model bake-off |
| RAG loop; Gradio | LlamaIndex; LangGraph agent |
| Chroma + metadata filters; upsert on refresh | Recommender |
| Vector search; parent doc = get_section; self-query ≈ regex+filters; HNSW default | FAISS second index; multi-query unless L1 citation-id is poor |

### Decision: slip order (unchanged)

1. Deontic retry (not a v1 spec MUST) 2. HTTP SSE / streaming the JSON answer bubble 3. Chunking B on A-series (keep B on TO) 4. Gold cap 30 5. Coverage gate is src >= 80%. Never cut: TO + post-TO ingest, resume+refresh CLI, last_refresh banner, cite-or-abstain, citation-id, unit tests, uv/ruff/mypy/pytest --cov, health HTTP 200 on empty index, polite download.

Deontic scan stays slip-first in design only.

## Risks / Trade-offs

- [Local `.env` hijacks origin or collector project] → require `PROD_BASE_URL` and `PROD_PHOENIX_PROJECT_NAME`; optional `PROD_PHOENIX_COLLECTOR_ENDPOINT` so laptop Phoenix is not the public-process collector; origin-match fail-fast; never default the project to `PHOENIX_PROJECT_NAME`.
- [Private layout leak] → tracked files say `PROD_BASE_URL` / `LIVE_EMAIL` / “public HTTPS origin” only.
- [OTP coalesce looks like a send] → fail unless a new IMAP UID ≥ request time.
- [1 send/email/minute] → overlap the gap with chat + collector poll; one extra wait at most.
- [httpx follows redirects] → wash GET sets `follow_redirects=False`.
- [Batch export lag / never flushed] → 90s poll; fail if missing. Do not add product `flush()`.
- [Collector empty project today] → suite fails closed until dump-host export to that project works (that is the check).
- [A 3500 silencio on a paid/local model blip] → fail, not skip; rerun. Do not weaken to “structured contract only”.
- [Shared process 20/60s and 30 chats/email/day] → two chats per run; sequential; fail-fast on 429.
- [TUI allowlist drift] → `commands.toml` argv must equal `ALLOWED_RUNNABLE`.
- [Coverage vs prod tests] → helpers live under `tests/`; fake-suite coverage gate unchanged.
- [Pytest collection order] → one module; later fixtures depend on earlier; tests do not send mail themselves.
- [Same client requests and consumes the link] → send 2 from client A; consume on cookie-less B.

## Migration Plan

1. Flag/marker/skip loop + fail-fast session checks (default pytest still green).
2. Login-URL parse + collector poll helpers with fakes/`respx`.
3. Prod smoke tests; document command and env (empty values in `.env.example`).
4. Operators export `PROD_BASE_URL`, matching `AUTH_PUBLIC_ORIGIN`, `PROD_PHOENIX_PROJECT_NAME`, plus existing IMAP and collector keys; run the command against the already-running public process.
5. Rollback: delete the change’s tests and catalog rows; no runtime migration.

## Open Questions

None that block apply. IMAP remains IMAPS 993 or plain IMAP (not STARTTLS), same as live. Operator schedule is out of repo.
