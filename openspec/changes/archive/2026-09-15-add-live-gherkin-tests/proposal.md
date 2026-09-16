## Why

Cited CAMEX clauses with visible guardrails and L1 numbers. Unit tests and in-process Gherkin inject `FakeMailer` and `TestClient`, so they never prove that the local uvicorn sends a real one-time secret, that Gradio’s login `fetch` sets a session, or that an authenticated chat turn against the operator’s language-model setting still returns a cited clause or honest silencio.

## What Changes

Nothing is **BREAKING** for `POST /chat`, cookies, or the observatory. Default `uv run pytest -q` and CI stay fake-only.

- An opt-in live Gherkin suite (pytest-bdd) hits the **already-running** local process (`LIVE_BASE_URL`, default `http://127.0.0.1:8000`). The suite does not spawn uvicorn.
- **HTTP** scenarios cover public health, authentication, unauthenticated 401, input guardrail blocks, and the authenticated chat JSON contract. Live Then phrases are unique so they do not collide with in-process Gherkin.
- **Observatory** scenarios drive Gradio in Chromium (Playwright): login row, Enviar/Clear while logged out, Usuario vs Staff chrome, canned prompts, inspector/trust, abstain banner, wide vs narrow viewport (Staff chrome only when authenticated).
- Authentication uses **real SMTP** (the process’s `AUTH_SMTP_*`) and **real IMAP** (test-only `LIVE_IMAP_*`) to read the 6-digit secret. The app does not gain an IMAP port. IMAPS on 993 is the default; `LIVE_IMAP_SSL=false` is plain IMAP, not STARTTLS.
- One allowlisted mailbox per run: HTTP scenarios share one SMTP send + IMAP read (or reuse an unused leftover secret), then reuse the session cookie (Playwright injects it). Cookie-less UI login MAY wait once on the per-email send gap and send once more. Sequential only.
- Chat generation uses the process’s existing `LLM_*` (xAI grok-4.3 **or** local llama.cpp Qwen3.6-35B-A3B). Assertions are structural, not exact clause text. Thinking chrome is asserted only when a thought region appears. Named A 3500 is skip/fail, not induced empty-index.
- New pytest flag `--run-live-server` and markers `live_server` / `live_http` / `live_ui`, distinct from `--run-integration` (live BCRA PDFs). Independent skip loops: missing flag skips; both flags run both suites. Flag set with a down server or missing IMAP **fails**.
- README `## How to run`, `.env.example`, `scripts/commands.toml`, and the TUI allowlist gain the live command and `playwright install chromium`. Playwright is a **dev** dependency.

## Capabilities

### New Capabilities

- `live-acceptance`: opt-in Gherkin against the running local process — real SMTP+IMAP authentication, HTTP chat/health, Playwright observatory — without requiring live mail, a browser, a language-model key, or uvicorn in the default test command.

### Modified Capabilities

- `platform`: the default automated-test command still runs unit and in-process Gherkin with fakes; it MUST NOT require a running server, live mail, a browser, or a language-model key. Live acceptance is a separate operator command. The live BCRA catalog download command MUST NOT execute live acceptance.

## Non-goals

- Banxico or any non-`bcra.gob.ar` corpus.
- Next.js v1.
- LlamaIndex.
- Redis.
- Filling the 1990–97 CAMEX catalog hole.
- GitHub-hosted vector index.
- An in-process SMTP/IMAP daemon.
- Spawning uvicorn from the test process.
- Running live mail, Chromium, or a paid/local language-model call in CI.
- Archiving `add-authentication` / `harden-authentication` into main specs.
- Gradio built-in login, OAuth, passwords, WebAuthn, TOTP.
- Exhausting send/verify/chat rate limits on the operator mailbox or process.
- Clock-dependent OTP expiry, five-failure burn, HTTPS `Secure` cookie, SMTP 503, overlapping concurrent send (remain unit-tested).
- STARTTLS on IMAP port 143.
- Inducing an empty index or proving `index_not_ready` against the live process (remain unit-tested).
- Ingest/refresh, chunking A/B, L1 evals, or Fake-LLM messy citation JSON as live scenarios.
- Multi-browser matrix, headed CI, or committing private hostnames / home paths.
- Changing canned prompt text, light theme, or English UI copy.
- A git-flow version bump.

## Impact

- New tests under `tests/features/live/` plus IMAP helper unit tests (fake mailbox in the default suite). Existing `tests/features/chat.feature` stays on fakes. Live Gherkin Then lines MUST NOT copy the in-process suite.
- Dev dependency: Playwright (Chromium). stdlib `imaplib` for mail. No new runtime package. Five RAG ports unchanged. No IMAP inside `bcra_rag.auth`.
- README How-to-run, `.env.example` (`LIVE_*` keys, origin/demo-key notes), `scripts/commands.toml`, and the local-dev TUI catalog allowlist. CI workflow unchanged. `src` coverage gate stays on the fake suite (>= 80%).
- Operators must have uvicorn up, SMTP configured, IMAP credentials, an allowlisted mailbox, HTTP-local `AUTH_PUBLIC_ORIGIN` matching `LIVE_BASE_URL`, and (for UI) Chromium. Chat/UI generation needs the process’s `LLM_*` and, for named-Com. A citations, a ready dump. A warm process may already have spent the chat limiter.
