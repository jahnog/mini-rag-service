## Why

Cited CAMEX clauses with visible guardrails and L1 numbers. Signing in still means typing a 6-digit code from mail, the session lasts a week, and one mailbox can spend the language-model budget without a daily ceiling — so login is harder than it needs to be and a stolen or shared session can drain the dump host.

## What Changes

- The one-time-secret mail SHALL include the 6-digit code **and**, when a public origin is configured, a login URL with a high-entropy token (not the digits). Token lifetime is the same 5 minutes as the code. First success (typed code **or** link) burns both.
- The login URL SHALL use a hybrid consume: the path that still contains the token never sets a session (it only stores an HTTP-only cookie and redirects). The same browser that requested the code MAY be signed in on the next hop when the request is a top-level navigation; any other client MUST confirm on a page that names the mailbox, then POST. GET hops from a mail client MUST NOT be rejected for origin (foreign Referer); confirm POST still MUST match the public origin. Typed OTP on the observatory remains. A coalesced live secret MUST keep the same login token and the same browser intent (double-send must not break one-tap).
- Mail SHALL be `multipart/alternative` (plaintext + HTML). Both parts carry the code and, when present, the URL. HTML follows the observatory look with inline CSS and email-client limits. The subject still MUST NOT contain the code or the token.
- **BREAKING (session lifetime):** new session credentials last **24 hours** (was 7 days). Already-issued cookies keep their stamped expiry. Logout on the observatory stays (signed-in email + `Cerrar sesión`); a link login MUST still land on that chrome.
- **BREAKING (chat budget):** authenticated chat SHALL refuse further language-model turns after **30** per normalized email per UTC day and after **100** per process per UTC day (HTTP 429, structured log, no language-model call). `/clear` and unauthenticated 401 MUST NOT consume those caps. The existing 20/60s per-client burst limit stays.

No JSON field changes on `/chat`. Ingest, `/health`, and the five RAG ports stay as they are.

## Capabilities

### New Capabilities

- (none)

### Modified Capabilities

- `authentication`: 24-hour session; high-entropy login token in the same mail as the 6-digit code; hybrid consume (token-path GET never authenticates; washed GET may auto-login only with a bound intent cookie and top-level navigation; otherwise confirm POST); GET login-link hops are not origin-checked; coalesce keeps token and intent; multipart mail; logs still MUST NOT persist token, code, or full email.
- `assistant-ui`: mail may include a login URL; a small confirm interstitial is allowed and MUST return to the observatory; typed OTP and logout remain on the same screen; Enviar on a chat cap shows a Spanish too-many-attempts notice.
- `platform`: 30 language-model turns per normalized email per UTC day and 100 per process per UTC day; unauthenticated requests and `/clear` do not consume them; a refuse is logged.

## Non-goals

- Banxico or any non-`bcra.gob.ar` corpus.
- Next.js v1.
- LlamaIndex.
- Redis.
- Filling the 1990–97 CAMEX catalog hole.
- GitHub-hosted vector index.
- CAPTCHA, OAuth, passwords, WebAuthn, TOTP, Gradio built-in login.
- A second product UI (the confirm page is an interstitial, then `/`).
- Two-role allowlists, opening `AUTH_ALLOWED_EMAILS=*`, persisting one-time secrets or counters on disk.
- Cookie denylist, uvicorn access-log redaction, DMARC/SPF (operator).
- CI-blocking live magic-link click or a paid L1 eval.
- Changing canned prompt text, light theme, or English UI copy.
- A git-flow version bump.

## Impact

- `bcra_rag.auth`: mail copy (plain + HTML), login-token map, intent/link cookies, `GET`/`POST /auth/link`, session Max-Age 86400. `handle_turn`: daily turn counters. Observatory Blocks tree unchanged except logout must still hydrate after a link login.
- Settings: `AUTH_SESSION_DAYS` default 1; `AUTH_PUBLIC_ORIGIN` also builds the mail URL; `CHAT_TURNS_PER_EMAIL_DAY` (30) and `CHAT_TURNS_PER_PROCESS_DAY` (100) on RAG settings. README `## How to run` and env examples document those.
- Tests: labeled OTP extractor (mail URL must not be mistaken for the 6-digit code); 24h cookie; wash/scanner/auto-login/confirm/origin; both mail parts; 30/100 caps and log outcomes. Default `uv run pytest -q` stays fakes-only. `src` coverage stays >= 80%. No new operator command.
