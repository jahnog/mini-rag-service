## Why

Cited CAMEX clauses with visible guardrails and L1 numbers. The observatory already accepts any well-formed mailbox in the login field, but a one-time secret is mailed only when that address is on `AUTH_ALLOWED_EMAILS`, so a visitor who is not on the list never signs in. Operators need an explicit opt-in to send codes to any address without turning an empty list into an accidental open relay.

## What Changes

- When the configured allowlist contains the token `*` (comma-separated, trimmed), the system SHALL send a one-time secret to any well-formed email if mail is configured and no send limit is exceeded.
- An empty allowlist SHALL still send nothing (fail closed). A concrete list without `*` SHALL still refuse unknown addresses with the same success shape as a send (no oracle).
- Send/verify limits, origin checks, SMTP fail-closed, OTP coalesce, session cookies, and Staff-for-every-authenticated-user stay as they are.
- README `## How to run` and env examples document `*` as the open-signup sentinel. No new operator command. No JSON schema change.

## Capabilities

### New Capabilities

- (none)

### Modified Capabilities

- `authentication`: allowlist token `*` sends a one-time secret to any well-formed email; empty list remains fail closed; concrete lists still hide misses.

## Non-goals

- Banxico or any non-`bcra.gob.ar` corpus.
- Next.js v1.
- LlamaIndex.
- Redis.
- Filling the 1990–97 CAMEX catalog hole.
- GitHub-hosted vector index.
- OAuth, passwords, WebAuthn, TOTP, or Gradio built-in login.
- A second UI or a dedicated login route.
- Two-role allowlists (staff vs end-user). Authenticated users may still open Staff.
- CAPTCHA, disposable-email blocklists, or persisting one-time secrets / send counters on disk.
- Changing canned prompt text, light theme, or English UI copy.
- Changing Spanish login copy (the generic “habilitado” status stays so a miss is not an oracle).
- Raising or removing send/verify limits.
- A git-flow version bump.

## Impact

- `bcra_rag.auth` allowlist match in the one-time-secret request path. HTTP `/auth/request` shape unchanged (`{"ok": true}` on send and on a concrete-list miss).
- Unit tests for `*` (any well-formed mailbox receives a code), empty still sends nothing, concrete miss still sends nothing. Live allowlist-miss scenarios still need a concrete list on the running process; `*` would send to the miss address.
- `.env.example`, `deploy/env.remote.example`, and README copy-env paragraph name `AUTH_ALLOWED_EMAILS=*` as open signup. SMTP must still be configured; the MTA must still relay to external domains.
- Five RAG ports, ingest/refresh, chat JSON, and observatory chrome are untouched. `src` coverage stays >= 80%.
