# Tasks — 07 conversation memory and phases

Requires changes 02 (10-tuple yields, `_pending_inspector`), 04 (`thinking=` keyword), 05/06 (`_prompt` signature with `chunk_chars`). Line anchors are as of this change's writing; grep the quoted symbol if they moved. `FakeLlm` records prompts in `llm.calls`, so prompt-content tests read `llm.calls[-1]`.

## 1. query-answering — memory in the prompt

- [x] 1.1 `src/bcra_rag/use_cases/answer_query.py`: add `HISTORY_TURNS = 2`, `HISTORY_MAX_CHARS = 300` and `history_block(...)` (design.md). `_prompt` gains `history: str = ""` and, when non-empty, inserts `f"Conversación previa (contexto, no fuente; no citar de acá):\n{history}\n\n"` after the `Pregunta:` block. `generate_from_context` gains `history: str = ""` and passes it to `_prompt`. In `_respond`, after `history = self._sessions.get(session_id)` (~line 206) keep the variable and pass `history=history_block(history)` to `generate_from_context`.
- [x] 1.2 Follow-up heuristic: add `_is_short_followup(message)` (design.md; import `named_ids` from `bcra_rag.domain.router`) and change `_compose_followup` to compose when `FOLLOW_RE.search(message) or _is_short_followup(message)`.
- [x] 1.3 Tests `tests/test_answer_query.py` (model on the existing "y ese punto?" tests, ~line 585-600; `_uc(tmp_path, llm=…)` returns `(use_case, sessions)`):
  ```python
  @pytest.mark.asyncio
  async def test_prior_exchange_reaches_prompt_as_context(tmp_path: Path) -> None:
      llm = FakeLlm(IN_CORPUS_DRAFT)
      use_case, _ = _uc(tmp_path, llm=llm)
      first = await use_case.run(ChatRequest(message="qué se exige para liquidar exportaciones"), request_id="h1")
      await use_case.run(ChatRequest(message="¿cuánto plazo?", session_id=first.session_id), request_id="h2")
      prompt = llm.calls[-1]
      assert "Conversación previa (contexto, no fuente" in prompt
      assert "Usuario: qué se exige para liquidar exportaciones" in prompt
      assert "Asistente: Los residentes deberán liquidar" in prompt
      assert "Pregunta:\nqué se exige para liquidar exportaciones\n¿cuánto plazo?" in prompt


  @pytest.mark.asyncio
  async def test_short_named_question_is_not_composed(tmp_path: Path) -> None:
      llm = FakeLlm(IN_CORPUS_DRAFT)
      use_case, _ = _uc(tmp_path, llm=llm)
      first = await use_case.run(ChatRequest(message="qué se exige para liquidar exportaciones"), request_id="n1")
      second = await use_case.run(ChatRequest(message="Comunicación A 3500?", session_id=first.session_id), request_id="n2")
      assert "Pregunta:\nComunicación A 3500?" in llm.calls[-1]
      assert any(g.rule == "retrieve" for g in second.guardrails)


  @pytest.mark.asyncio
  async def test_cleared_session_has_no_history_block(tmp_path: Path) -> None:
      llm = FakeLlm(IN_CORPUS_DRAFT)
      use_case, _ = _uc(tmp_path, llm=llm)
      first = await use_case.run(ChatRequest(message="qué se exige para liquidar exportaciones"), request_id="c1")
      await use_case.run(ChatRequest(message="/clear", session_id=first.session_id), request_id="c2")
      await use_case.run(ChatRequest(message="qué se exige para liquidar exportaciones", session_id=first.session_id), request_id="c3")
      assert "Conversación previa" not in llm.calls[-1]
  ```
  Keep `test_followup_weather_after_camex_blocks_scope` and friends green (scope still runs on `ctx.raw`). Verify: `uv run pytest tests/test_answer_query.py -q` → passes.

## 2. query-answering — phase callback

- [x] 2.1 `answer_query.py`: add `OnPhase = Callable[[str], Awaitable[None]]`, `PHASE_RETRIEVE = "retrieve"`, `PHASE_GENERATE = "generate"`, `PHASE_VERIFY = "verify"`, and
  ```python
  async def _emit(on_phase: OnPhase | None, code: str) -> None:
      if on_phase is None:
          return
      try:
          await on_phase(code)
      except Exception:
          return
  ```
  `AnswerQuery.run(..., on_phase: OnPhase | None = None)` → `_respond(..., on_phase=on_phase)`; in `_respond` call `await _emit(on_phase, PHASE_RETRIEVE)` immediately before the `Router(...).route(...)` call; pass `on_phase=on_phase` to `generate_from_context`, which gains `on_phase: OnPhase | None = None` and calls `await _emit(on_phase, PHASE_GENERATE)` before `_complete_with_retry` and `await _emit(on_phase, PHASE_VERIFY)` before `pipeline.run_named(output_ids, ctx, short_circuit=False)`.
- [x] 2.2 `src/bcra_rag/api/handle.py`: `run_prepared_turn` and `handle_turn` gain `on_phase: OnPhase | None = None` and forward it (import `OnPhase` from `bcra_rag.use_cases.answer_query`).
- [x] 2.3 Tests `tests/test_answer_query.py`:
  ```python
  @pytest.mark.asyncio
  async def test_phases_reported_in_order(tmp_path: Path) -> None:
      use_case, _ = _uc(tmp_path, llm=FakeLlm(IN_CORPUS_DRAFT))
      seen: list[str] = []

      async def on_phase(code: str) -> None:
          seen.append(code)

      await use_case.run(ChatRequest(message="qué se exige hoy para liquidar el cobro de exportaciones"), request_id="p", on_phase=on_phase)
      assert seen == ["retrieve", "generate", "verify"]
      seen.clear()
      await use_case.run(ChatRequest(message="What's the weather in Madrid?"), request_id="p2", on_phase=on_phase)
      assert seen == []


  @pytest.mark.asyncio
  async def test_phase_callback_error_does_not_fail_turn(tmp_path: Path) -> None:
      use_case, _ = _uc(tmp_path, llm=FakeLlm(IN_CORPUS_DRAFT))

      async def boom(code: str) -> None:
          raise RuntimeError(code)

      response = await use_case.run(ChatRequest(message="qué se exige hoy para liquidar el cobro de exportaciones"), request_id="p3", on_phase=boom)
      assert response.citations
  ```
  Verify: `uv run pytest tests/test_answer_query.py -k phase -q` → passes.

## 3. assistant-ui — phase line and throttle

- [x] 3.1 `src/bcra_rag/ui/config.py`: add `PHASE_COPY = {"retrieve": "Buscando en el dump…", "generate": "Redactando respuesta…", "verify": "Verificando citas…"}`; change `THOUGHT_PUBLISH_S = 0.12` to `0.5`; `append_pending(history, user, thinking="", *, title: str = THOUGHT_PENDING_TITLE)` uses `title` for the pending row.
- [x] 3.2 `src/bcra_rag/ui/gradio_app.py`:
  - add `def _phase_update(text: str) -> Any: return gr.update(value=text, visible=bool(text))`.
  - `iter_observatory_turn`: add `phase = [""]`, `last_trace = [""]`; closure
    ```python
    async def on_phase(code: str) -> None:
        phase[0] = PHASE_COPY.get(code, "")
        event.set()
    ```
    pass `on_phase=on_phase` in the `run_turn(...)` call (both layouts); in `on_thinking` publish when `thought_publish_ready(text) and now - last_pub[0] >= THOUGHT_PUBLISH_S` or `now - last_pub[0] >= 2 * THOUGHT_PUBLISH_S`; every `yield` appends `_phase_update(phase[0])` as the 11th element (first yield: `_phase_update("")`; pending yields use `append_pending(snapshot, message, thinking=trace, title=phase[0] or THOUGHT_PENDING_TITLE)`; in the loop also yield a pending row when the phase changed even if `staff` is false or the trace is empty — track `last_phase[0]`; skip a thinking yield when `trace == last_trace[0]` and the phase did not change); final, HTTP-error and generic-error yields append `_phase_update("")`.
  - `build_blocks`: after `chatbot = gr.Chatbot(...)` add `phase_box = gr.Markdown("", elem_id="turn-phase", visible=False)`; append `phase_box` as the last entry of `outputs`; `_clear` returns `rows, sid, *_empty_inspector(), _phase_update("")`; add `"turn-phase"` to the elem-id list in `tests/test_ui.py::test_build_blocks_does_not_call_run_l1`.
  - `run_turn` inner function accepts `on_phase: OnPhase | None = None` and forwards it to `handle_turn`.
- [x] 3.3 `src/bcra_rag/ui/observatory.css`: add `#turn-phase` to the transparent-block selector list (the one containing `#chat-kicker`, `#auth-status`) and a rule
  ```css
  #turn-phase p {
    margin: 0;
    color: var(--wl-muted);
    font-size: var(--wl-text-sm);
    font-style: italic;
    border-left: 2px solid var(--wl-gold);
    padding-left: var(--wl-space-3);
    animation: thought-pulse 1.4s ease-in-out infinite;
  }
  ```
  and add `#turn-phase p { animation: none; }` inside the existing `@media (prefers-reduced-motion: reduce)` block. `tests/test_ui.py::test_observatory_css_tokens`: assert `"#turn-phase" in css`.
- [x] 3.4 Tests `tests/test_ui.py`: update every fake `run_turn` in the iterator tests (~line 497-690) to `async def run_turn(*, message, session_id, on_thinking=None, on_phase=None)`; add
  ```python
  @pytest.mark.asyncio
  async def test_iter_turn_phase_line_in_usuario_layout() -> None:
      async def run_turn(*, message, session_id, on_thinking=None, on_phase=None):
          del message, session_id, on_thinking
          await on_phase("retrieve")
          await on_phase("generate")
          return _turn_response()

      yields = [item async for item in iter_observatory_turn("hola", None, None, run_turn=run_turn, staff=False)]
      phases = [y[10] for y in yields]
      assert any(getattr(p, "get", lambda k, d=None: None)("value") == "Buscando en el dump…" or (isinstance(p, dict) and p.get("value") == "Buscando en el dump…") for p in phases)
      assert yields[-1][10]["visible"] is False
      assert all("Buscando" not in str(row.get("content", "")) for row in yields[-1][0])
  ```
  (check how other tests read `gr.update(...)` results — they are dicts with `value`/`visible` keys; simplify the assertion accordingly.) Add `test_iter_turn_staff_pending_title_follows_phase`: staff run where `on_phase("generate")` fires before `on_thinking("x")`; the pending row title in the corresponding yield is "Redactando respuesta…". Add `test_iter_turn_skips_unchanged_trace`: `on_thinking("a ")` twice yields one pending redraw. Keep `tests/test_ui.py:407` ("Pensando…" default) green. Verify: `uv run pytest tests/test_ui.py -q` → passes.

## 4. Spec sync and gates

- [x] 4.1 Sync deltas into `openspec/specs/{query-answering,assistant-ui}/spec.md`.
- [x] 4.2 `uv run ruff check .`; `uv run mypy src`; `uv run pytest -q --cov=src --cov-report=term-missing` → green, ≥ 80%.
- [x] 4.3 Operator check: Usuario turn shows "Buscando en el dump…" then "Redactando respuesta…" under the chat and hides on answer; Staff pending title changes with the phase; ask "¿cuánto plazo?" after an exports question and confirm the prompt in `data/logs/chat.log` is not needed — instead confirm the answer stays on topic and cites the dump.
