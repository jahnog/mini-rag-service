# Tasks — 02 observatory inspector state

Requires change 01 (tooling green). Line anchors are as of this change's writing; grep the quoted symbol if they moved. Output tuple order for every yield of `iter_observatory_turn` is `(chatbot, session_state, inspector, trust, abstain_box, copy_id, citation_choice, cards_state, card_md, trust_box)`.

## 1. assistant-ui — inspector follows the conversation

- [ ] 1.1 In `src/bcra_rag/ui/gradio_app.py::iter_observatory_turn` (search `cards = citation_cards(outcome) if staff else []`, ~line 326) replace the three gated lines with:
  ```python
  cards = citation_cards(outcome)
  inspector = inspector_payload(outcome)
  trust = trust_payload(outcome)
  ```
  Leave `thinking = thinking_for_staff(outcome.thinking, staff=staff)` and `on_thinking=on_thinking if staff else None` unchanged.

- [ ] 1.2 Update `tests/test_ui.py::test_iter_turn_usuario_hides_thinking_and_inspector` (~line 633): replace `assert yields[-1][2] == {}` with
  ```python
  assert yields[-1][2] != {}
  assert yields[-1][3]  # trust rows computed even in Usuario
  ```
  and rename the test to `test_iter_turn_usuario_hides_thinking_but_keeps_inspector`. Keep the assertions that `"trace secreto"` is absent from the rows. Verify: `uv run pytest tests/test_ui.py -k usuario -q` → passes.

## 2. assistant-ui — in-progress placeholders

- [ ] 2.1 In `src/bcra_rag/ui/config.py`, right after `EMPTY_TRUST = …` (~line 24), add:
  ```python
  PENDING_CITATION_CARD = "Buscando citas…"
  PENDING_TRUST = '<p class="obs-empty">Guardrails en curso…</p>'
  TURN_FAILED_NOTICE = "Error interno al responder. Probá de nuevo."
  ```
- [ ] 2.2 In `gradio_app.py`, import the three constants from `bcra_rag.ui.config` (the import block at ~line 29-71, alphabetical) and add below `_empty_inspector` (~line 346):
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
  Change the first yield of `iter_observatory_turn` (~line 246) to `yield (append_pending(snapshot, message), session_id, *_pending_inspector())`. Intermediate yields (~lines 288-300) keep `_skipped_inspector()`.
- [ ] 2.3 Test in `tests/test_ui.py` (next to `test_iter_turn_yields_thinking_before_answer`, ~line 498):
  ```python
  @pytest.mark.asyncio
  async def test_iter_turn_first_yield_shows_pending_inspector() -> None:
      async def run_turn(*, message, session_id, on_thinking=None):
          del message, session_id
          if on_thinking is not None:
              await on_thinking("pensando algo")
          return _turn_response(thinking="pensando algo")

      yields = [item async for item in iter_observatory_turn("hola", None, None, run_turn=run_turn)]
      first = yields[0]
      assert first[8] == PENDING_CITATION_CARD
      assert first[9] == PENDING_TRUST
      assert first[2] == {} and first[3] == []
      middle = [y for y in yields[1:-1]]
      assert all(isinstance(y[8], type(gr.skip())) for y in middle)
      assert yields[-1][8] != PENDING_CITATION_CARD
  ```
  Import `PENDING_CITATION_CARD`, `PENDING_TRUST` from `bcra_rag.ui.config` and `import gradio as gr` at the top of the test module if missing (check how other tests reference `gr.skip()`; if none do, assert instead `middle[0][8] is not None and middle[0][8] != PENDING_CITATION_CARD`). Verify: `uv run pytest tests/test_ui.py -k pending_inspector -q` → passes.

## 3. assistant-ui — error paths

- [ ] 3.1 In `gradio_app.py`, above `TurnRunner = …` (~line 106) add:
  ```python
  @dataclass(frozen=True)
  class InspectorPrior:
      inspector: dict[str, Any]
      trust: list[dict[str, str]]
      cards: list[dict[str, Any]]
      choice: str | None
  ```
  (`from dataclasses import dataclass`). Extend `_choice_update` (~line 90) to `def _choice_update(choices: list[str], *, value: str | None = None) -> Any:` returning `value=value if value in choices else (choices[0] if choices else None)`.
- [ ] 3.2 Add `prior: InspectorPrior | None = None` to the keyword parameters of `iter_observatory_turn` (after `staff: bool = True`). Add a helper below `_pending_inspector`:
  ```python
  def _prior_inspector(prior: InspectorPrior | None) -> tuple[Any, ...]:
      if prior is None or not prior.inspector and not prior.trust:
          return _empty_inspector()
      choices = [str(card["id"]) for card in prior.cards]
      return (
          prior.inspector,
          prior.trust,
          _abstain_update("", visible=False),
          _copy_update(str(prior.inspector.get("copy_id") or "")),
          _choice_update(choices, value=prior.choice),
          prior.cards,
          citation_card_markdown(prior.inspector or None),
          trust_markdown(prior.trust or None),
      )
  ```
  Replace the `HTTPException` branch (~line 310-314) body's `*_empty_inspector()` with `*_prior_inspector(prior)`. Replace `if isinstance(outcome, BaseException): raise outcome` (~line 315-316) with:
  ```python
  if isinstance(outcome, BaseException):
      _LOG.warning("observatory_turn_failed", error=type(outcome).__name__)
      rows = append_messages(snapshot, message, TURN_FAILED_NOTICE)
      yield (rows, session_id, *_empty_inspector())
      return
  ```
  with `_LOG = structlog.get_logger(__name__)` at module level (`import structlog`; check how other modules create loggers, e.g. `grep -rn "structlog.get_logger" src/bcra_rag | head -3`, and copy that style).
- [ ] 3.3 In `build_blocks._turn` (~line 380): add parameters `inspector_prior: dict[str, Any] | None, trust_prior: list[dict[str, str]] | None, cards_prior: list[dict[str, Any]] | None, choice_prior: str | None` after `layout`, before `request`; build `prior = InspectorPrior(inspector=dict(inspector_prior or {}), trust=list(trust_prior or []), cards=list(cards_prior or []), choice=choice_prior)` and pass `prior=prior` to `iter_observatory_turn`. Update both event wirings (~lines 642, 647) to `inputs=[msg, chatbot, session_state, demo_box, layout_choice, inspector, trust, cards_state, citation_choice]`.
- [ ] 3.4 Tests in `tests/test_ui.py` next to `test_iter_turn_http_error_drops_thought` (~line 563):
  ```python
  @pytest.mark.asyncio
  async def test_iter_turn_http_error_keeps_prior_inspector() -> None:
      async def run_turn(*, message, session_id, on_thinking=None):
          del message, session_id, on_thinking
          raise HTTPException(status_code=429, detail="rate limited")

      prior = InspectorPrior(
          inspector={"id": "A8359", "copy_id": "A8359", "snippet": "texto"},
          trust=[{"rule": "scope", "verdict": "pass", "stage": "input", "detail": "", "enforced": "true", "would_block": "false"}],
          cards=[{"id": "A8359", "copy_id": "A8359", "snippet": "texto"}],
          choice="A8359",
      )
      yields = [item async for item in iter_observatory_turn("hola", None, None, run_turn=run_turn, prior=prior)]
      last = yields[-1]
      assert "Demasiados intentos" in last[0][-1]["content"]
      assert last[2] == prior.inspector
      assert "A8359" in last[8]
      assert "scope" in last[9]


  @pytest.mark.asyncio
  async def test_iter_turn_generic_error_replaces_pending_row() -> None:
      async def run_turn(*, message, session_id, on_thinking=None):
          del message, session_id, on_thinking
          raise RuntimeError("boom")

      yields = [item async for item in iter_observatory_turn("hola", None, None, run_turn=run_turn)]
      last = yields[-1]
      assert last[0][-1]["content"] == TURN_FAILED_NOTICE
      assert "metadata" not in last[0][-1]
      assert last[8] == EMPTY_CITATION_CARD
  ```
  Import `InspectorPrior` from `bcra_rag.ui.gradio_app` and `TURN_FAILED_NOTICE` from `bcra_rag.ui.config`. Also extend `test_build_blocks_does_not_call_run_l1` (search `def test_build_blocks_does_not_call_run_l1`): no change to elem ids is needed; keep it green. Verify: `uv run pytest tests/test_ui.py -k "iter_turn" -q` → all pass.

## 4. assistant-ui — unknown verdict style

- [ ] 4.1 `src/bcra_rag/ui/config.py::trust_markdown` (~line 401): `cls = verdict if verdict in _TRUST_VERDICTS else "skipped"`.
- [ ] 4.2 Test next to `test_inspector_copy_id_and_trust` (~line 778):
  ```python
  def test_trust_markdown_unknown_verdict_is_skipped_style() -> None:
      html_out = trust_markdown([{"rule": "x", "verdict": "weird", "stage": "input", "detail": "", "enforced": "true", "would_block": "false"}])
      assert 'obs-chip skipped' in html_out
      assert 'obs-chip pass' not in html_out
  ```
  Verify: `uv run pytest tests/test_ui.py -k unknown_verdict -q` → passes.

## 5. assistant-ui — send-code copy from the TTL

- [ ] 5.1 `src/bcra_rag/ui/config.py`: replace `AUTH_STATUS_SMTP_OK = "Código enviado"` (~line 49) with
  ```python
  def auth_status_smtp_ok(ttl_s: int) -> str:
      minutes = max(1, round(ttl_s / 60))
      return (
          "Listo. Si pediste un código hace menos de "
          f"{minutes} minutos, usá ese; si no, revisá tu correo."
      )


  AUTH_STATUS_SMTP_OK = auth_status_smtp_ok(300)
  ```
  (place the function above the constant block or keep it after `AUTH_NOTICE`; the constant must be defined after the function).
- [ ] 5.2 `gradio_app.py`: wrap the `_AUTH_REQUEST_JS` template (~line 108-206) in `def auth_request_js(smtp_ok: str) -> str:` that returns the same string with `.replace("__AUTH_SMTP_OK__", json.dumps(smtp_ok, ensure_ascii=False))`; keep `_AUTH_REQUEST_JS = auth_request_js(AUTH_STATUS_SMTP_OK)` at module level. In `build_blocks`, change `send_code.click(..., js=_AUTH_REQUEST_JS)` (~line 692-697) to `js=auth_request_js(auth_status_smtp_ok(auth.settings.otp_ttl_s))` and import `auth_status_smtp_ok`.
- [ ] 5.3 Tests in `tests/test_ui.py`: `test_auth_js_posts_token_email_request` (~line 1030) keeps passing unchanged (constant still substituted). Add:
  ```python
  def test_auth_status_smtp_ok_names_window() -> None:
      assert auth_status_smtp_ok(300) == (
          "Listo. Si pediste un código hace menos de 5 minutos, usá ese; si no, revisá tu correo."
      )
      assert "10 minutos" in auth_status_smtp_ok(600)
      assert "1 minutos" in auth_status_smtp_ok(20)
      assert "Código enviado" not in auth_request_js(auth_status_smtp_ok(300))
  ```
  Verify: `uv run pytest tests/test_ui.py -k "auth_status or auth_js" -q` → passes; `uv run pytest tests/test_auth.py tests/test_auth_http.py -q` → unchanged, passes.

## 6. assistant-ui — desktop rail scroller

- [ ] 6.1 `src/bcra_rag/ui/observatory.css`, inside `@media (min-width: 64rem) {` find `#observatory-side {` (grid-area/sticky rule) and add after `top: var(--wl-space-4);`:
  ```css
    max-height: calc(100dvh - 2 * var(--wl-space-4));
    overflow-y: auto;
    overscroll-behavior: contain;
  ```
- [ ] 6.2 `tests/test_ui.py::test_observatory_css_tokens` (~line 158-161): replace `assert "overflow-y: auto" not in css` with
  ```python
  before_desktop, _, desktop = css.partition("@media (min-width: 64rem)")
  assert "overflow-y: auto" not in before_desktop
  assert desktop.count("overflow-y: auto") == 1
  assert "overscroll-behavior: contain" in desktop
  ```
  Keep `assert "max-height: 100dvh" not in css` (the new value is `calc(100dvh - …)`, which does not match that literal). Verify: `uv run pytest tests/test_ui.py::test_observatory_css_tokens -q` → passes.

## 7. Gates and visual check

- [ ] 7.1 `uv run ruff check .`; `uv run mypy src`; `uv run pytest -q --cov=src --cov-report=term-missing` → green, ≥ 80%.
- [ ] 7.2 Operator visual check (server started by the operator, `./run.sh` or `uv run uvicorn bcra_rag.api.app:app --port 8000`; sign in via the mail link): (a) Usuario turn → switch to Staff → inspector shows that turn; (b) Staff turn → "Buscando citas…" / "Guardrails en curso…" appear immediately; (c) trigger the IP limiter with 21 quick sends → notice shown, previous card kept; (d) 1280×800 window → rail scrolls internally; 375-wide → no internal scrollbar; (e) send code twice within 5 minutes → both times the "Listo. Si pediste un código…" line.
