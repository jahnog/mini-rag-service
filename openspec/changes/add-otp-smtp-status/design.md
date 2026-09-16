## Context

See proposal.md Why. Five ports stay five (Catalog, Extractor, Index, Llm, SessionStore). Composition root, ingest/refresh, router, chunking A/B, session memory, and host-side refresh are unchanged. IBM 1–4 take/leave and slip-first deontic scan are unchanged.

The login row already has `#auth-status` (`gr.Markdown`) and `send_code.click(None, js=_AUTH_REQUEST_JS)` posting `POST /auth/request`. HTTP 200 is dummy-success on allowlist miss / unconfigured mailer / coalesced live secret. SMTP fail-closed is HTTP 503. Gradio 6 js-only events (`fn=None`) are off `demo.queue()`, have no backend spinner, and do not debounce `trigger_mode=once`.

## Goals / Non-Goals

**Goals:**
- Map HTTP 200 → delivered copy, HTTP 503 / `fetch` throw → not-delivered copy, flash ~2s on `#auth-status`, restore idle hint if the line is still that SMTP result.
- Keep 429 / 403 / 422 until the next auth action.
- Keep `{ok: true}` and the allowlist oracle.

**Non-Goals:**
- Python `.then()` + sleep (would occupy the Gradio queue and stall chat).
- Changing `auth/service.py` or `routes.py`.
- Inbox/IMAP proof. Distinguishing dummy-200 from a real SMTP 250.

## Decisions

### Decision: Same `#auth-status` slot, client-side flash

Return the SMTP line from `_AUTH_REQUEST_JS` so Gradio sets Markdown. Paint `Enviando…` on the inner `p` / `.md` during `fetch` (no spinner), then paint the result after `fetch` so a skipped Gradio update cannot leave `Enviando…` stuck. After 2000 ms, restore `AUTH_STATUS_GENERIC` only if the visible text is still this click’s message (Verificar / logout also write this Markdown). Token `window.__authSendToken`; disable `#auth-send` during `fetch`.

Alternative: toast overlay — rejected (second surface). Alternative: `asyncio.sleep` on a Python `.then()` — rejected (queue stall). Alternative: flash 429 too — rejected (Retry-After can be 60s).

### Decision: Copy in `bcra_rag.ui.config`, inject with `json.dumps`

`AUTH_STATUS_SMTP_OK`, `AUTH_STATUS_SMTP_FAIL`, `AUTH_STATUS_SENDING`, `AUTH_STATUS_FLASH_MS = 2000`. Keep `AUTH_STATUS_GENERIC`. Do not f-string the JS (it is full of `{ }`). Do not return HTML (Markdown sanitizes).

Delivered: `Código enviado`. Fail (HTTP 503): `No se pudo enviar el código`. Network or unexpected status: `Problemas enviando el código`. Sending: `Enviando…`.

### Decision: Dummy 200 still looks delivered

`sent: true/false` would oracle the allowlist. Unconfigured `AUTH_SMTP_HOST` also dummy-200s; operators with a host set and a real SMTP error still get 503. This is SMTP accept, not IMAP.

### Decision: Color via classes, not HTML

`#auth-status.auth-status-ok` → `var(--success)`; `.auth-status-err` → `var(--danger)`. Re-apply after Gradio paints (`setTimeout(0)`). 429/403/422/idle/sending have no ok/err class. `aria-live="polite"` once on `#auth-status`.

## Risks / Trade-offs

- [Dummy 200 says delivered when nothing hit SMTP] → existing no-oracle; do not add a sent flag.
- [2s timer overwrites Verificar] → revert only if visible text equals this click’s SMTP line.
- [Double-click on js-only] → token + disable `#auth-send` during fetch.
- [Svelte resets classes on the Block] → re-apply ok/err after paint; never `innerHTML` the Block root.
- [Gradio value stays on the SMTP line after DOM revert] → next send/verify/logout overwrites; acceptable.

## Migration Plan

Deploy with the observatory UI. Rollback is revert the three UI files. No schema, cookie, or SMTP setting change.

## Open Questions

None.
