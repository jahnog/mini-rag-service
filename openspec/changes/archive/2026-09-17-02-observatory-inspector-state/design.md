## Context

See proposal.md Why. Five ports stay five. The UI is a Gradio 6 Blocks app; every turn is `iter_observatory_turn` (`src/bcra_rag/ui/gradio_app.py:236-343`) yielding a 10-tuple in the order of `outputs` (`:628-639`): `chatbot, session_state, inspector, trust, abstain_box, copy_id, citation_choice, cards_state, card_md, trust_box`. `_empty_inspector()` (`:346-356`) returns the 8 inspector values; `_skipped_inspector()` (`:359-361`) returns 8 `gr.skip()`.

Facts as of this change's writing:
- `:246` first yield: `(append_pending(snapshot, message), session_id, *_skipped_inspector())`.
- `:288-292` and `:296-300` intermediate yields use `_skipped_inspector()`.
- `:310-314` `HTTPException` → `append_messages(snapshot, message, notice)` + `_empty_inspector()`; `:315-316` other `BaseException` → `raise outcome`.
- `:326-328` `cards = citation_cards(outcome) if staff else []`, `inspector = inspector_payload(outcome) if staff else {}`, `trust = trust_payload(outcome) if staff else []`.
- `_turn` (`:380-426`) has inputs `[msg, chatbot, session_state, demo_box, layout_choice]` (`:642,:647`).
- `ui/config.py:401` `cls = verdict if verdict in _TRUST_VERDICTS else "pass"`.
- `ui/config.py:49` `AUTH_STATUS_SMTP_OK = "Código enviado"`; `_AUTH_REQUEST_JS` (`gradio_app.py:107-206`) substitutes `__AUTH_SMTP_OK__` with `json.dumps(AUTH_STATUS_SMTP_OK)`; `send_code.click(None, inputs=[auth_email], outputs=[auth_status], js=_AUTH_REQUEST_JS)` at `:692-697`. `AuthSettings.otp_ttl_s` (`auth/settings.py:26`, default 300).
- `observatory.css` desktop block `@media (min-width: 64rem)` sets `#observatory-side { grid-area: side; position: sticky; top: var(--wl-space-4); }`. `tests/test_ui.py:158-161` asserts `"overflow-y: auto" not in css` (whole file).
- Tests: `test_iter_turn_usuario_hides_thinking_and_inspector` (`tests/test_ui.py:633-654`) asserts `yields[-1][2] == {}`; `test_iter_turn_http_error_drops_thought` (`:563-584`); `test_auth_js_posts_token_email_request` (`:1030-1049`) asserts `AUTH_STATUS_SMTP_OK in _AUTH_REQUEST_JS`.

## Goals / Non-Goals

**Goals:** inspector state mirrors the conversation; no stale or lying UI state during/after a turn; honest send-code copy; usable rail on short desktop viewports.

**Non-Goals:** changing what Staff sees for a successful turn; any server/auth change; client JS.

## Decisions

### Decision: Compute inspector payloads in every layout; hide by layout only

`iter_observatory_turn` always calls `citation_cards`, `inspector_payload`, `trust_payload`. Only `thinking_for_staff(outcome.thinking, staff=staff)` and the `on_thinking` wiring remain layout-gated. The side column is already `visible=False` in Usuario (`apply_layout`), so nothing new is shown to end users. Rationale: all users are authenticated (`prepare_turn` returns 401 otherwise), so there is no confidentiality boundary between layouts; the spec sentence "MUST NOT fill the citation inspector or the per-query guardrail log" is narrowed to the thinking trace. Alternative: `gr.skip()` inspector on Usuario turns — rejected (Staff would later see chips from an older turn than the answer).

### Decision: In-progress placeholders on the first yield

New helper in `gradio_app.py`:
```python
def _pending_inspector() -> tuple[Any, ...]:
    return (
        {},
        [],
        _abstain_update("", visible=False),
        _copy_update(""),
        _choice_update([]),
        [],
        PENDING_CITATION_CARD,
        PENDING_TRUST,
    )
```
with constants in `ui/config.py`:
```python
PENDING_CITATION_CARD = "Buscando citas…"
PENDING_TRUST = '<p class="obs-empty">Guardrails en curso…</p>'
```
Used only in the first yield; intermediate thinking yields keep `_skipped_inspector()`.

### Decision: Errors keep or reset the inspector explicitly

`iter_observatory_turn` gains a keyword `prior: InspectorPrior | None = None` where
```python
@dataclass(frozen=True)
class InspectorPrior:
    inspector: dict[str, Any]
    trust: list[dict[str, str]]
    cards: list[dict[str, Any]]
    choice: str | None
```
- `HTTPException` (401/429/…): rows = `append_messages(snapshot, message, notice)`; inspector tuple re-emits the prior: `(prior.inspector, prior.trust, _abstain_update("", visible=False), _copy_update(prior.inspector.get("copy_id") or ""), _choice_update([c["id"] for c in prior.cards], value=prior.choice), prior.cards, citation_card_markdown(prior.inspector or None), trust_markdown(prior.trust or None))`; when `prior is None` fall back to `_empty_inspector()`.
- Any other `BaseException`: log `structlog.get_logger().warning("observatory_turn_failed", error=type(exc).__name__)`, rows = `append_messages(snapshot, message, TURN_FAILED_NOTICE)` with `TURN_FAILED_NOTICE = "Error interno al responder. Probá de nuevo."`, emit `_empty_inspector()`, do not re-raise. `asyncio.CancelledError` is still re-raised inside `produce()` (unchanged).
`_turn` reads the prior from four extra inputs (`inspector, trust, cards_state, citation_choice`) and builds `InspectorPrior`. `_choice_update` must accept `value=`; check its current signature and extend with `value: str | None = None` if absent.

### Decision: Unknown verdict → `skipped`

`cls = verdict if verdict in _TRUST_VERDICTS else "skipped"`.

### Decision: Coalesce-aware send-code copy from the TTL

```python
def auth_status_smtp_ok(ttl_s: int) -> str:
    minutes = max(1, round(ttl_s / 60))
    return (
        "Listo. Si pediste un código hace menos de "
        f"{minutes} minutos, usá ese; si no, revisá tu correo."
    )

AUTH_STATUS_SMTP_OK = auth_status_smtp_ok(300)
```
`_AUTH_REQUEST_JS` becomes the result of `auth_request_js(smtp_ok: str) -> str` (same template, `__AUTH_SMTP_OK__` replaced by `json.dumps(smtp_ok, ensure_ascii=False)`), and the module keeps `_AUTH_REQUEST_JS = auth_request_js(AUTH_STATUS_SMTP_OK)` so existing tests and imports work. `build_blocks` wires `js=auth_request_js(auth_status_smtp_ok(auth.settings.otp_ttl_s))`. Server and `tests/test_auth*.py` untouched; the wording is true for a real send, a coalesce, and an allowlist miss, so it leaks nothing.

### Decision: Desktop-only internal scroller for the rail

Inside the existing `@media (min-width: 64rem)` block:
```css
  #observatory-side {
    grid-area: side;
    position: sticky;
    top: var(--wl-space-4);
    max-height: calc(100dvh - 2 * var(--wl-space-4));
    overflow-y: auto;
    overscroll-behavior: contain;
  }
```
The phone principle (page is the only scroller) is preserved because the rule lives in the desktop block. `tests/test_ui.py:158-161` changes from a whole-file ban to: the text before `@media (min-width: 64rem)` contains no `overflow-y: auto`, and the text after it contains exactly one. Alternative: no sticky — rejected (approved layout); JS sticky-to-bottom — rejected (no new client JS).

## Risks / Trade-offs

- [Prior inspector re-emitted after 429 refers to an older question] → acceptable; the chat shows the limit notice as the latest row and the card is unchanged rather than blanked.
- [`_choice_update(value=…)` may not restore selection in Gradio Radio when choices are unchanged] → cosmetic; card markdown is re-emitted explicitly.
- [Internal scroller hides the accordion at first glance] → a scrollbar appears; L1 is last by design.

## Migration Plan

UI-only; deploy with the observatory. Rollback = revert the three UI files.

## Open Questions

None.
