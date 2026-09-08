## Context

See proposal.md Why and the delta specs under `specs/live-acceptance/` and `specs/platform/`.

Product runtime already exists. Unchanged architecture (restated so this design satisfies the constitution):

- **Ports:** Catalog, Extractor, Index (owns embeddings), Llm, SessionStore. This change does **not** add a port. IMAP is test-only; `bcra_rag.auth` still sends with `SmtpMailer` only.
- **Composition:** `build_ingest` / `build_app`; no DI container. Live tests do not call `build_app`. They speak HTTP/HTML to the operator’s already-running `uvicorn bcra_rag.api.app:app`.
- **Ingest/refresh pipeline:** catalog → polite fetch → classify → extract → chunk A/B → index upsert → MANIFEST checkpoint. Untouched.
- **Router / chunking / session:** aliases; named Com. A `get_section` vs vigente (TO ∪ later A’s); serving uses structured chunker B on TO + clean A’s and fixed A otherwise; in-process session (last six messages), one worker, `/clear`. Chat memory stays bound to the authenticated email.
- **Host-side refresh:** systemd oneshots + cron.d on the dump host (not GitHub Actions). Untouched.

Constraints: Python 3.11+ via uv; pytest + pytest-bdd already in the dev group; FastAPI + Gradio mounted at `/`; no private hostnames in tracked files (`tests/test_no_private_layout.py`); default pytest and CI stay fake-only; `src` coverage >= 80% on the fake suite.

Today: `tests/features/chat.feature` drives `AnswerQuery` / `TestClient` with `FakeMailer` and `FakeLlm`. `tests/conftest.py` `--run-integration` is live BCRA PDF ingest, not this suite. Auth unit tests never open SMTP or IMAP.

## Goals / Non-Goals

**Goals:**

- Opt-in Gherkin against the running local process: HTTP (`/health`, `/auth/*`, `/chat`, `/chat/clear`) and observatory UI.
- Real SMTP (process `AUTH_SMTP_*`) + real IMAP (test `LIVE_IMAP_*`) for the 6-digit secret.
- Playwright Chromium for Gradio login chrome, Usuario/Staff, Enviar/Clear, inspector/trust, viewports.
- Keep default `uv run pytest -q` and GitHub Actions fake-only.
- Unit-test IMAP parse/poll helpers with a fake mailbox so the default suite still covers that code.

**Non-Goals:**

- Spawning uvicorn; in-process SMTP/IMAP daemon.
- IMAP inside `bcra_rag.auth`; a sixth port; Redis.
- CI live mail, Chromium, or language-model calls.
- Archiving `add-authentication`.
- Exhausting rate limits; clock-dependent OTP expiry; HTTPS Secure; SMTP 503.
- STARTTLS on IMAP port 143.
- Inducing an empty index; proving `index_not_ready` live.
- Ingest/L1/chunking live scenarios; Fake-LLM messy JSON.
- Naming private llama.cpp hostnames in committed files.
- Next.js, LlamaIndex, Banxico, 1990–97 hole, GitHub-hosted vector index.

## Decisions

### Decision: attach to uvicorn, do not spawn

`LIVE_BASE_URL` default `http://127.0.0.1:8000`. Session-scoped health GET; if `--run-live-server` and connect fails → **fail**. No `subprocess.Popen(uvicorn)`.

Fail-fast before IMAP or Chromium:

- `LIVE_BASE_URL` MUST origin-match `AUTH_PUBLIC_ORIGIN` (scheme+host+port). Mismatch is a fixture error naming both URLs, not an IMAP timeout.
- Live suite is HTTP-local: `AUTH_PUBLIC_ORIGIN` must be `http://…`. If public origin is `https://`, `cookie_secure` is true even on loopback and Chromium will not store a `Secure` cookie from `http://127.0.0.1`.
- `DEMO_API_KEY` MUST be unset, or sent as `x-demo-key` / Gradio demo box. `handle_turn` still checks it after the session.
- Unauthenticated `POST /chat/clear` MUST send `{"session_id": …}`; omitting it is FastAPI 422, not 401.

Alternatives: spawn from `.env` (port fights, two processes, not “the local dev server”); TestClient (does not prove SMTP, Gradio JS, or the operator LLM).

### Decision: `--run-live-server` is not `--run-integration`

Extend `tests/conftest.py` with two **independent** skip loops. Never return early from `pytest_collection_modifyitems`:

- `--run-live-server`
- markers `live_server`, `live_http`, `live_ui` (all live tests also have `live_server`), registered in `pyproject.toml` next to `integration` / `bdd`

Without `--run-live-server`, skip `live_server`. Without `--run-integration`, skip `integration`. If both flags are passed, both suites run. `pytest --run-live-server` without `-m` still skips `integration`. `--run-integration` still skips `live_server`.

With `--run-live-server`, missing server or `LIVE_IMAP_*` **fails**. Chromium missing: `live_ui` fails with `playwright install chromium`; `-m live_http` can still pass.

Every live `.feature` MUST have Feature-level tags `@live_server` plus `@live_http` or `@live_ui` so pytest-bdd puts those names in `item.keywords`. Missing tags would execute live scenarios on default pytest.

Command (README + `scripts/commands.toml`, `confirm = true`):

```bash
uv run pytest --run-live-server -m live_server -q
```

That argv MUST also be added to `scripts/devtui.py` `ALLOWED_RUNNABLE` (`load_catalog()` requires runnable argv to equal that frozenset). Keep `block`/`id` aligned with the README `test-live-server` fence.

CI `.github/workflows/test.yml` unchanged. `tests/test_ci_workflow.py` stays “no live BCRA/embeddings”; do not require it to mention the live flag.

### Decision: stdlib IMAP, test-only env, no auth port

New helper (e.g. `tests/features/live/mailbox.py`): `imaplib` + `email`. IMAPS on 993 (`LIVE_IMAP_SSL` default true) uses `IMAP4_SSL`. `LIVE_IMAP_SSL=false` is plain `IMAP4`; the operator sets `LIVE_IMAP_PORT` (typically 143). It is **not** STARTTLS (`IMAP4` then `starttls()` is unsupported).

Poll INBOX (or `LIVE_IMAP_MAILBOX`) for subject `Tu código de BCRA Mini-RAG`, parse `\b(\d{6})\b` from text body, assert subject has no 6-digit token, mark/delete after a successful verify. Timeout ~30s, poll ~1s. Allowlist-miss wait ~10s then assert no **new** OTP message (Date/`INTERNALDATE` ≥ request time), not empty inbox.

Env (`.env.example` only, not `AuthSettings`):

- `LIVE_BASE_URL`
- `LIVE_IMAP_HOST` / `PORT` (993) / `USER` / `PASSWORD` / `MAILBOX` (INBOX) / `SSL` (true)
- `LIVE_EMAIL` (allowlisted; default IMAP user)

Unit tests feed a fake IMAP mailbox (no network). Production `SmtpMailer` unchanged.

Alternatives: `aiosmtpd` in-process (not the operator’s real servers); app IMAP port (wrong hexagon).

### Decision: one shared session cookie; at most one extra SMTP send for cookie-less UI login

OTP is single-use; 1 send/email/60s; plus-tags collapse. Unused OTP is reused, not rotated (`AuthService._request_otp_locked` returns 200 without SMTP when a live unused code exists).

HTTP session-scoped fixture:

1. `POST /auth/request` with `Origin`/`Referer` = `LIVE_BASE_URL` (must match `AUTH_PUBLIC_ORIGIN`).
2. If a new IMAP UID arrives with `Date`/`INTERNALDATE` ≥ request time and subject `Tu código de BCRA Mini-RAG`, use that body code.
3. Else search recent UNSEEN with that subject within OTP TTL (~300s) and reuse the leftover 6-digit code. HTTP 200 with no new mail is success. Do not treat coalesce as a send failure or IMAP timeout. Do not search the whole mailbox history.
4. `POST /auth/verify`; keep `httpx.Client` cookies; mark/delete the used IMAP message.

Playwright `browser.new_context()` then `add_cookies` for that `session` cookie (name from `AUTH_COOKIE_NAME` / Set-Cookie, domain from `LIVE_BASE_URL`). Most observatory scenarios start authenticated.

Cookie-less contexts: logged-out load, Enviar while logged out, unauthenticated Staff, suggested prompts, UI login-with-mailed-code.

UI “login with mailed code” (proof that Gradio `fetch` sets a session): cookie-less context **after** the HTTP fixture has verified (OTP consumed; IMAP message marked/deleted). Wait `Retry-After` or 60s **once**, click Enviar código once, IMAP-read only a **new** UID ≥ the click time, click Verificar. Do **not** fall back to leftover UNSEEN (that code is consumed). Do not click Enviar código immediately; Gradio JS on 429 only shows “Demasiados intentos. Probá más tarde.” HTTP-only runs (`-m live_http`) never start Chromium, so no second SMTP send.

Logout HTTP scenario uses a **clone** of the client (cookie copy) so it does not steal the shared session from later chat tests. It does not send mail.

Single-use: wait ≥ `min_verify_interval_s` (2s) then second `POST /auth/verify` with the recorded digits on a fresh client. Faster replay is HTTP 429, not invalid-code.

Alternatives: two mailboxes (operator burden); UI-only login (HTTP-only runs could not auth); skip cookie-less UI login (would not prove Gradio `fetch`).

### Decision: httpx + pytest-bdd; Playwright as a dev extra

- HTTP: `httpx.Client` (already a runtime dep), cookie jar, JSON.
- UI: `playwright` in the **dev** group; Chromium only; headless. pytest fixture wraps `sync_playwright`. Do not add `pytest-playwright` unless apply shows pytest-bdd needs it.
- Features under `tests/features/live/`: `auth_http.feature`, `chat_http.feature`, `auth_ui.feature`, `observatory_ui.feature`. Step module(s) there. Existing `tests/features/chat.feature` untouched.
- pytest-bdd 8.1 registers `given`/`when`/`then` process-wide. Live Then phrases MUST be unique. They MUST NOT copy `tests/features/chat.feature` / `tests/features/test_chat_bdd.py` strings. Required HTTP phrases: `the HTTP finding is silencio` / `the HTTP finding is not silencio`; `the HTTP no-advice rule is block`; `the HTTP injection rule is block`; `the HTTP scope rule is block`; `the HTTP answer does not reveal hidden instructions`; `an HTTP citation id is "A3500"`. Also do not reuse `the HTTP status is {n}`, `the user asks "{message}"`, `the user clears the session`, `the clear response has no citations`. Keep spec wording such as `the response is HTTP 401` and `the acknowledgement has no retrieved citations`. `-m live_server` does not help: pytest still imports `test_chat_bdd.py` during collection.
- Locators: `#auth-email`, `#auth-send`, `#auth-code`, `#auth-verify`, `#auth-logout`, `#auth-status`, `#observatory-chat`, `#observatory-input`, `#observatory-send`, `#observatory-clear`, `#observatory-side`, `#observatory-freeze`, `#trust-panel`, `#l1-panel`, `#abstain-banner`, Vista radio `Staff (IA)` / `Usuario`. Apply adds `#observatory-input` / `#observatory-send` / `#observatory-clear` on the question box, Enviar, and Clear (they have no `elem_id` today). Gradio wraps textboxes — target the inner `input`/`textarea`. Spanish copy from `bcra_rag.ui.config` (`AUTH_NOTICE`, `AUTH_SEND`, …).
- Viewports: 1280×720 and 375×812. Staff layout bounding boxes of `#observatory-stage` vs `#observatory-side` run only after cookie inject **and** Vista is `Staff (IA)`. `#observatory-side` is created `visible=False`; cookie-less Staff is the hide-chrome scenario only.
- Canned prompts: assert the four `CANNED_PROMPTS` strings (including A 9999). Do not assert dump-answerability (that would be three extra LLM calls). Looking at pills does not call `handle_turn`.
- Prior turns are Gradio widget state, not `SessionStore`. HTTP `POST /chat` will not fill the chatbot. Seed weather by typing and clicking Enviar **in that Playwright context** (guardrail block, no LLM). Share one authenticated context for Staff/Usuario toggle + in-corpus + A 9999; seed weather once there. Logout/Clear-keeps-turns: cloned context, cookie inject, its own UI weather seed, then logout, then Clear.

`playwright install chromium` documented under Setup/Test in README `## How to run`.

### Decision: structural live asserts; no `llm.calls`

Live Then-steps use status, JSON fields, guardrail verdicts, visible text, IMAP. They do **not** scrape `chat.log` to prove the model was not called.

Named Com. A 3500 skip/fail matrix (HTTP and Usuario/Staff in-corpus UI):

- skip when `GET /health` reports `index_ready` false (do not induce an empty index)
- skip when finding is `silencio` and `abstain_reason` is `llm_unavailable` or `missing_document`
- **fail** when `index_ready` is true and finding is `silencio` with any other reason, including `cite-or-abstain`
- when finding is not `silencio`, require citation id `A3500`

Invented A 9999: skip only when `index_ready` is false. Do **not** skip on `missing_document` (A 3500 missing and A 9999 share that reason; for A 9999 it is the expected silencio). Citations empty.

Input blocks (no-advice, injection, scope) do not need a ready index and stay hard.

HTTP 429 from the process 20/60s limiter is a **fail-fast fixture error** naming the limiter (restart the process or wait), not a silent skip. `/chat` and `/chat/clear` both go through `handle_turn`. Logged-out Enviar 401s before the limiter. Sequential only. Expected live runtime: one OTP + optional 60s UI gap + a handful of LLM calls (`LLM_TIMEOUT_S` default 60s plus slack). A fresh process fits ~12 `handle_turn`s; a warm operator session may already have spent the window.

Thinking: if `.thought-group` exists, it must not contain `Fuente:`. Absence is OK (xAI grok-4.3 may omit a trace; llama.cpp Qwen with `LLM_ENABLE_THINKING=true` often has one). Do not pin `LLM_MODEL` in tests. Do not write private hostnames.

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

- [One mailbox + single-use OTP] → HTTP fixture one send or leftover reuse; Playwright `add_cookies`; UI login waits at most once on the 60s gap and must not reuse the consumed IMAP message.
- [AUTH_PUBLIC_ORIGIN rejects httpx / Secure cookie on HTTPS public origin] → fail-fast naming both URLs; live suite is HTTP-local.
- [Allowlist-miss IMAP false fail] → bound wait; assert no **new** OTP subject, not empty inbox.
- [Gradio shadow/iframe locators] → `elem_id` + inner input; if apply flakes, pin `frame_locator` once in the helper, not in every step.
- [Gradio chatbot vs SessionStore] → seed prior turns in the same Playwright context; HTTP chat does not fill the widget.
- [LLM silencio on named A 3500] → skip only `llm_unavailable` / `missing_document` / unreadiness; `cite-or-abstain` fails so the live command cannot go green without seeing `A3500`.
- [A 9999 shares `missing_document` with missing A 3500] → skip that reason only for A 3500.
- [Thinking missing on grok-4.3] → optional thought-group assert.
- [Shared process rate limits] → sequential; fail-fast on 429; do not loop 20 chats or 5 emails.
- [Playwright in default collection] → skip without `--run-live-server` before launching a browser; Feature tags required.
- [pytest-bdd duplicate steps] → unique live phrases; default `uv run pytest -q` must still collect.
- [TUI allowlist drift] → `commands.toml` argv must equal `ALLOWED_RUNNABLE`.
- [Coverage vs live tests] → live files are tests, not `src`; fake-suite coverage gate unchanged.
- [Private layout leak] → document “local llama.cpp Qwen3.6-35B-A3B or xAI grok-4.3 via `LLM_*`” only.

## Migration Plan

1. Land harness + IMAP helper + unit tests (default pytest still green).
2. Add live Gherkin; skip without the flag; unique step phrases.
3. Document command, `LIVE_*`, origin/demo-key notes, `playwright install chromium`; TUI allowlist.
4. Operators already running uvicorn + SMTP keep `.env`; add IMAP keys; set `AUTH_PUBLIC_ORIGIN` to the HTTP loopback origin used as `LIVE_BASE_URL`.
5. Rollback: delete the change’s tests and the Playwright dev extra; no runtime migration.

## Open Questions

- None that block apply. Cookie-less UI login wait is “wait once, new UID only”. IMAP is IMAPS 993 or plain IMAP; not STARTTLS.
