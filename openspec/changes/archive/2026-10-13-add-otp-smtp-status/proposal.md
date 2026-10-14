## Why

Cited CAMEX clauses with visible guardrails and L1 numbers. After Enviar código the login row repeats the idle hint on HTTP 200, and SMTP fail-closed shows as “Autenticación no configurada,” so a payments/FX person cannot tell whether the one-time secret was handed to the mail server.

## What Changes

- After Enviar código, the same-screen status message SHALL show for about two seconds whether the one-time secret was accepted by the mail server (delivered vs not delivered), in Spanish, then return to the idle hint unless a later login action already replaced the line.
- HTTP 200 (including allowlist miss and a coalesced live secret) SHALL use the delivered wording. HTTP 503 or a failed request SHALL use the not-delivered wording.
- Rate-limit, origin, and invalid-email notices SHALL remain until the next auth action (not the two-second flash).
- Authentication HTTP contract, allowlist oracle, and mail fail-closed stay as they are. No second UI.

## Capabilities

### New Capabilities

- (none)

### Modified Capabilities

- `assistant-ui`: login-row status after send-code reports mail-server accept or fail for about two seconds, then restores the idle Spanish hint unless verify or logout already replaced it.

## Non-goals

- Banxico or any non-`bcra.gob.ar` corpus.
- Next.js v1.
- LlamaIndex.
- Redis.
- Filling the 1990–97 CAMEX catalog hole.
- GitHub-hosted vector index.
- Changing allowlist, OTP coalesce, SMTP timeout, or `{ok: true}` shape.
- Inbox/IMAP proof in this flash.
- Auto-clear of Verificar / Cerrar sesión status.
- Captcha, OAuth, passwords, or a second UI.
- A git-flow version bump.

## Impact

- Observatory login chrome only (`ui/config.py`, `ui/gradio_app.py` JS for Enviar código, `observatory.css`). No RAG port, chat JSON, or auth protocol change.
- Unit tests on Spanish copy and the send-code JS (flash duration, SMTP ok/fail, 429 stays). Default `uv run pytest -q` stays fakes. `src` coverage stays >= 80%.
- No new operator command; README `## How to run` unchanged.
