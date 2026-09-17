## Why

Cited CAMEX clauses with visible guardrails and L1 numbers. In the observatory the side inspector (citations, guardrail log) does not follow the conversation: a turn made in the Usuario layout empties it (`trust_payload(outcome) if staff else []`, `ui/gradio_app.py:328`), so switching back to Staff shows "Sin guardrails todavía." for a live conversation; while a new turn streams, the previous turn's chips stay under the "Pensando…" row (`gr.skip()` on every intermediate yield); an HTTP 401/429 wipes the inspector and any other exception leaves the pending row and stale chips in place; an unknown verdict string is painted green (`cls = … else "pass"`, `ui/config.py:401`). Two smaller defects share the same surface: after Enviar código the status says "Código enviado" even when the server coalesced a live secret and mailed nothing (deliberate anti-enumeration in `auth/service.py:97-100`), and on desktop the sticky inspector can be taller than the viewport (18 chips ≈ 1550 px vs 1250 px), hiding its lower part until the page end.

## What Changes

- The citation inspector and guardrail log SHALL be computed for every turn in every layout; the layout only decides whether they are shown. Only the thinking trace stays off the wire in Usuario. (MODIFIED `assistant-ui` "Staff payloads stay off the wire in Usuario".)
- At the start of a turn the inspector SHALL show in-progress placeholders ("Buscando citas…", "Guardrails en curso…") instead of the previous turn's content.
- On HTTP 401/429 the inspector SHALL keep the previous turn's content; on any other failure the pending row SHALL be replaced by a Spanish notice and the inspector reset, without an unhandled exception.
- Unknown verdicts SHALL render with the `skipped` style, never `pass`.
- The send-code success status SHALL be true for all HTTP 200 cases and SHALL name the coalesce window derived from `otp_ttl_s`.
- On desktop widths the inspector column SHALL scroll internally when taller than the viewport; phones keep the page as the only scroller.

## Capabilities

### New Capabilities

- (none)

### Modified Capabilities

- `assistant-ui`: inspector follows the conversation in both layouts; in-progress placeholders; error handling keeps or resets the inspector; unknown verdict styling; coalesce-aware send-code copy; desktop rail scroller.

## Non-goals

- Banxico or any non-`bcra.gob.ar` corpus.
- Next.js v1.
- LlamaIndex.
- Redis.
- Filling the 1990–97 CAMEX catalog hole.
- GitHub-hosted vector index.
- Changing the auth protocol, the OTP coalesce, or the `{ok: true}` response.
- Client-side JavaScript beyond the existing auth snippets (no sticky-rail script).
- Streaming the final answer (see change 07 for phase indicators).

## Impact

- `src/bcra_rag/ui/gradio_app.py` (`iter_observatory_turn`, `_turn` inputs, `_pending_inspector`), `src/bcra_rag/ui/config.py` (constants, `trust_markdown`, `auth_status_smtp_ok`), `src/bcra_rag/ui/observatory.css` (64rem block), `tests/test_ui.py`.
- Spec: `assistant-ui` MODIFIED requirements listed above.
- No new command; README unchanged. Coverage stays ≥ 80% (UI module is fully unit-tested with fakes).
