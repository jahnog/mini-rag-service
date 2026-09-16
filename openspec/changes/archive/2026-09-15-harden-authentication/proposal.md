## Why

Cited CAMEX clauses with visible guardrails and L1 numbers. The new email session still ships a 7-day cookie without `Secure` behind TLS-terminating nginx, replaces a live one-time secret on every later request, keys chat memory only by a client `session_id`, and wipes the observatory on unauthenticated Clear — so a stolen HTTP cookie, a guessed allowlisted mailbox, or a shared browser can spend the language-model budget or leak prior turns.

## What Changes

- Session cookies SHALL be marked `Secure` when the public origin, a trusted forwarded proto, the request `Origin`/`Referer`, or the request URL is HTTPS. Logout SHALL clear that cookie with the same flag. Local HTTP without those signals stays non-Secure.
- A later request for a mailbox that already has an unexpired unused one-time secret SHALL return the same success shape, SHALL NOT send mail, and SHALL NOT consume send limits (**replaces** “later request replaces previous secret”).
- Mail send SHALL time out; a failed send SHALL NOT install an undelivered secret, SHALL count as a send attempt, and SHALL fail closed (HTTP 503) without naming the mailbox.
- Chat turn memory SHALL be bound to the authenticated email. The public `session_id` stays a UUID on the wire. A different mailbox that reuses that id MUST NOT see the prior turns. Same mailbox + same id still resumes. Logout still MUST NOT clear the observatory conversation by itself.
- When a public origin is configured, state-changing `/auth` POSTs SHALL match scheme, hostname, and port (default 443/80 equivalent to omitted), not hostname alone.
- Unauthenticated Clear SHALL keep prior turns and show the Spanish sign-in notice. Authenticated Clear still empties the conversation.
- One-time-secret maps and send counters SHALL be safe under concurrent request/verify on the serving process.

No **BREAKING** JSON field changes. `POST /chat` still requires a session. Ingest, `/health`, and the five RAG ports stay as they are.

## Capabilities

### New Capabilities

- (none)

### Modified Capabilities

- `authentication`: Secure session cookie; coalesce live one-time secrets; SMTP timeout and fail-closed send; origin match includes scheme and port; concurrent request/verify safety.
- `platform`: chat session memory is per authenticated email; public `session_id` remains a UUID; unauthenticated 401 still does not write memory.
- `assistant-ui`: unauthenticated Clear keeps turns and shows the sign-in notice; authenticated Clear still empties.

## Non-goals

- Banxico or any non-`bcra.gob.ar` corpus.
- Next.js v1.
- LlamaIndex.
- Redis.
- Filling the 1990–97 CAMEX catalog hole.
- GitHub-hosted vector index.
- Server-side cookie revoke tables, CAPTCHA, two-role allowlists, OAuth, passwords, WebAuthn, TOTP, Gradio built-in login.
- uvicorn `--proxy-headers`.
- Redacting `thinking` from authenticated `POST /chat` JSON.
- Changing canned prompt text, light theme, or English UI copy.
- A git-flow version bump.

## Impact

- `bcra_rag.auth` (cookie flags, origin helper, OTP coalesce, SMTP timeout, in-process lock). `handle_turn` scopes chat `SessionStore` keys by email. Observatory Clear uses a shared helper and keeps history on 401.
- New setting `AUTH_SMTP_TIMEOUT_S` (default 10). README How-to-run and env examples document public-origin `https://` for `Secure` cookies and that `session_id` is not portable across mailboxes.
- Tests cover Secure/non-Secure cookies, origin scheme/port, coalesce, SMTP 503, concurrent send, cross-mailbox chat, and logged-out Clear. `src` coverage stays >= 80%. No new operator command.
