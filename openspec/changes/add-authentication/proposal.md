## Why

Cited CAMEX clauses with visible guardrails and L1 numbers. The observatory is public, Staff (IA) is the default, and anyone can POST a query — so a casual visitor sees operator chrome and can spend the language-model budget. Staff debug belongs behind a signed-in session; queries must not run anonymously.

## What Changes

**BREAKING:** `POST /chat` and `POST /chat/clear` SHALL reject unauthenticated clients (HTTP 401) without retrieval, without a language-model call, and without writing chat session memory. Request and response JSON schemas are unchanged. `GET /health` stays public.

- Default the assistant to the **Usuario** layout. Only an authenticated session may switch to **Staff (IA)**.
- Email one-time secret: the user enters an email, the system emails a random 6-digit code that expires in 5 minutes, and the same code authenticates them. The session lasts 7 days.
- Only emails on a configured allowlist receive a code. An empty allowlist sends nothing (fail closed). Every authenticated user may chat in Usuario and may open Staff — one list, not two roles.
- Limits on sending codes: no more than 5 distinct emails per client per day; no more than 1 code per email per minute; plus tighter caps (per-email day, per-client day, verify failures, process-wide send ceiling) so mail cannot be used as an open relay.
- Same-screen login and logout (Spanish). No second product UI. Gradio built-in login is not used (it would lock the whole app).
- The assistant queue and the HTTP chat endpoints share the same authentication check. Protecting only HTTP would leave the website able to query.
- Implement authentication as a **new vertical module** (own settings, mail, one-time secrets, session credential, `/auth` HTTP). The five RAG ports stay five; chat and the observatory only ask that module whether a session is valid.
- README `## How to run` documents the new auth settings and that chat requires a session.

## Capabilities

### New Capabilities

- `authentication`: email 6-digit one-time secret, 5-minute code lifetime, 7-day session, allowlist, send/verify limits, logout, fail-closed when the signing secret or mail is missing, and the rule that chat turns require a valid session.

### Modified Capabilities

- `assistant-ui`: default layout is Usuario; login chrome is visible while logged out; Enviar/Clear do not produce a CAMEX answer until authenticated; Staff (IA) chrome (thinking, inspector, guardrail log, Calidad L1, dump freeze chips) applies only when authenticated; layout switch still does not clear the conversation.
- `platform`: chat and chat-clear reject unauthenticated clients without retrieval or a language-model call; health stays public; the existing per-client chat rate limit still applies after authentication; an optional shared demo secret remains an extra gate when set, not a substitute for the session.

## Non-goals

- Banxico or any non-`bcra.gob.ar` corpus.
- Next.js v1.
- LlamaIndex.
- Redis.
- Filling the 1990–97 CAMEX catalog hole.
- GitHub-hosted vector index.
- OAuth, passwords, WebAuthn, TOTP, or Gradio built-in login.
- A second UI or a dedicated login route.
- Two-role allowlists (staff vs end-user). Authenticated users may open Staff.
- CAPTCHA, disposable-email blocklists, or persisting one-time secrets / send counters on disk.
- Anonymous public chat.
- Changing canned prompt text, light theme, or English UI copy.
- A git-flow version bump.

## Impact

- New authentication HTTP endpoints (request code, verify, logout, session probe). Chat HTTP becomes session-gated (**BREAKING** for scripts and tests that posted without a session).
- Observatory topbar: default Usuario, login/logout row, server-enforced Staff switch. The shared turn handler rejects missing sessions before rate limit, retrieval, and generation.
- Mail adapter (tests fake it; production sends SMTP). In-process one-time secrets and send counters (same single-worker constraint as chat memory). Signed session cookie; no Redis.
- Unit tests for codes, limits, 401 chat, UI default/login/Staff gating; Gherkin chat scenarios authenticate first and add an unauthenticated 401 case. `src` coverage stays >= 80%.
- Env examples and README `## How to run` gain auth settings. No new operator command unless a setup step is added; the copy-env paragraph documents the keys.
- Five existing ports stay. Mail, OTP, cookies, and `/auth` live inside the new authentication module, not on the RAG hexagon. Ingest/refresh, router, and chunking are untouched.
