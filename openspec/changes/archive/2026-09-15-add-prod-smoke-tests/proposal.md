## Why

Cited CAMEX clauses with visible guardrails and L1 numbers. Local live Gherkin proves SMTP+IMAP OTP and chat against HTTP-local uvicorn, so a down public origin, a broken login link, a missing A 3500 citation, or a collector that never ingested the turn can all look healthy until an operator notices by hand.

## What Changes

Nothing is **BREAKING** for `POST /chat`, cookies, or the observatory. Default `uv run pytest -q` and CI stay fake-only.

- An opt-in production-smoke command hits the **already-running** public process (`PROD_BASE_URL`). The suite does not spawn uvicorn and does not use Chromium.
- **HTTP** scenarios cover public health (fail closed when the index is not ready), typed one-time secret, login-link confirm, named Comunicación A 3500, and out-of-scope weather. Assertions are structural (citation id, finding, guardrail rule), not exact clause text.
- Authentication uses **real SMTP** (the process’s `AUTH_SMTP_*`) and **real IMAP** (test-only `LIVE_IMAP_*` / `LIVE_EMAIL`). Each auth path waits for a **new** mailbox message (no leftover UNSEEN reuse). OTP and link each consume their own send. The app does not gain an IMAP port.
- After the two chat turns, the suite polls the configured collector REST host until matching `chat.turn` traces appear (question text on `input.value`; retrieve child on the relevant turn; scope child on the weather turn). A missing endpoint, project, or span within the poll bound **fails**.
- New pytest flag `--run-prod-smoke` and marker `prod_smoke`, distinct from `--run-live-server` and `--run-integration`. Independent skip loops. Flag set with a down origin, origin mismatch, missing IMAP, or missing collector **fails**.
- README `## How to run`, `.env.example`, `scripts/commands.toml`, `AGENTS.md`, and the TUI allowlist gain the command. Tracked files MUST NOT name the public hostname or mailbox. CI workflow unchanged.

## Capabilities

### New Capabilities

- `prod-smoke`: opt-in HTTP smoke against the running public process — real SMTP+IMAP typed secret and login-link confirm, named Com. A citation, out-of-scope silencio, collector traces — without requiring live mail, a collector, or a public origin in the default test command.

### Modified Capabilities

- `platform`: production smoke is a separate operator command and MUST NOT run as part of the default test command, the default CI workflow, live local-acceptance, or catalog download. The existing fakes-only default test command is unchanged.

## Non-goals

- Banxico or any non-`bcra.gob.ar` corpus.
- Next.js v1.
- LlamaIndex.
- Redis.
- Filling the 1990–97 CAMEX catalog hole.
- GitHub-hosted vector index.
- Playwright / Gradio observatory scenarios.
- Spawning uvicorn from the test process.
- An in-process SMTP/IMAP daemon; IMAP inside `bcra_rag.auth`.
- Leftover UNSEEN OTP reuse (local live suite may still coalesce).
- Allowlist-miss, logout matrix, injection/no-advice extras, invented A 9999, `/clear`.
- GitHub Actions schedule or dump-host timer (operator runs the command).
- A product-side tracer `flush()`.
- Reading dump-host `chat.log` over SSH.
- Committing the public hostname or mailbox.
- The PyPI package named `phoenix` (2013 Habbo client).
- Running live mail, a paid language-model call, or a collector in CI.
- Archiving `add-live-gherkin-tests` / `add-authentication` into main specs.
- Changing canned prompt text, light theme, or English UI copy.
- A git-flow version bump.

## Impact

- New tests under `tests/prod/` plus unit tests for login-URL parse and collector poll (fake mailbox / `respx` in the default suite). Existing `tests/features/live/` stays the local HTTP-local Gherkin suite.
- No new runtime package. Collector poll uses `httpx`. Five RAG ports unchanged.
- README How-to-run, `.env.example` (`PROD_BASE_URL`, `PROD_PHOENIX_PROJECT_NAME`; Origin must match), `scripts/commands.toml`, `AGENTS.md`, and the local-dev TUI catalog allowlist. CI workflow unchanged. `src` coverage gate stays on the fake suite (>= 80%).
- Operators must set `PROD_BASE_URL` and pytest-process `AUTH_PUBLIC_ORIGIN` to that same origin, IMAP credentials, an allowlisted mailbox, `PHOENIX_COLLECTOR_ENDPOINT`, and `PROD_PHOENIX_PROJECT_NAME`. Chat generation uses the process’s `LLM_*`. A warm process may already have spent the chat limiter or the per-email send gap.
