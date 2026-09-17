# Tasks — 09 turn caps, eval gate and observability

Requires changes 01, 04 (`run_prepared_turn` keyword shape), 07 (`on_phase`). Line anchors are as of this change's writing; grep the quoted symbol if they moved. `make_client(tmp_path, settings=…, index=…)` from `tests/chat_fixtures.py` builds an authenticated `TestClient`; the HTTP `/chat` body streams JSON (read `response.json()` after completion as the existing cap tests do).

## 1. platform — limiter before caps, refund on input block

- [x] 1.1 `src/bcra_rag/api/turn_caps.py`: add
  ```python
  def release(self, email: str) -> None:
      day = datetime.fromtimestamp(self.time_fn(), tz=UTC).strftime("%Y-%m-%d")
      email_key = (email, day)
      if self._email_day.get(email_key, 0) > 0:
          self._email_day[email_key] -= 1
      if self._process_day.get(day, 0) > 0:
          self._process_day[day] -= 1
  ```
  (check whether `allow` normalizes the email — plus-tag collapsing — and apply the same normalization in `release`; grep `normalize` in the module.)
- [x] 1.2 `src/bcra_rag/api/handle.py::prepare_turn` (~line 53-60): move the `if not limiter.allow(client_id): raise HTTPException(429, …)` block above the `turn_caps.allow` block. `run_prepared_turn` gains `turn_caps: TurnCaps | None = None`; after `response = await use_case.run(...)`:
  ```python
  if turn_caps is not None and (message or "").strip().lower() != "/clear":
      blocked_input = any(
          item.stage == "input" and item.verdict == "block" and item.enforced
          for item in response.guardrails
      )
      if blocked_input:
          turn_caps.release(prepared.email)
          _log.info("chat_cap_refund", email_hash=hashlib.sha256(prepared.email.encode()).hexdigest()[:8])
  ```
  `handle_turn` passes `turn_caps=turn_caps`; `src/bcra_rag/api/routes.py` `/chat` route passes `turn_caps=api.state.turn_caps` to `run_prepared_turn`.
- [x] 1.3 Tests `tests/test_chat_api.py` (next to `test_email_turn_cap_is_429`, ~line 268):
  ```python
  def test_scope_blocked_turn_is_refunded(tmp_path: Path) -> None:
      settings, index, _ = seed_ready(tmp_path)
      settings = settings.model_copy(update={"chat_turns_per_email_day": 2, "chat_turns_per_process_day": 10})
      client, llm, _, _ = make_client(tmp_path, settings=settings, index=index)
      for _ in range(2):
          assert client.post("/chat", json={"message": "What's the weather in Madrid?"}).status_code == 200
      answered = client.post("/chat", json={"message": "Qué es el MULC?"})
      assert answered.status_code == 200
      assert len(llm.calls) == 1


  def test_burst_limited_request_does_not_consume_cap(tmp_path: Path) -> None:
      settings, index, _ = seed_ready(tmp_path)
      settings = settings.model_copy(update={"rate_limit_requests": 1, "rate_limit_window_s": 60, "chat_turns_per_email_day": 1, "chat_turns_per_process_day": 10})
      client, _, _, _ = make_client(tmp_path, settings=settings, index=index)
      assert client.post("/chat", json={"message": "Qué es el MULC?"}).status_code == 200
      assert client.post("/chat", json={"message": "Qué es el MULC?"}).status_code == 429
      caps = client.app.state.turn_caps
      assert caps.allow(AUTH_EMAIL) == "email_cap"   # exactly one counted turn, not two
  ```
  (adapt the last assertion to how `test_turn_caps_reset_next_utc_day` at ~line 378 inspects `caps`; the point is that the burst-refused request did not increment the email counter.) Verify: `uv run pytest tests/test_chat_api.py -q` → passes.

## 2. platform / query-logging — background judge

- [x] 2.1 `src/bcra_rag/use_cases/answer_query.py`: add module-level `_BACKGROUND: set[asyncio.Task[None]] = set()` and `async def drain_turn_evals() -> None` (design.md). Refactor `AnswerQuery.run` (~line 82-128) per design.md: synchronous close when `isinstance(self._evaluator, NoOpTurnEvaluator)` or the generate step did not pass; otherwise schedule `self._score_and_close(...)`:
  ```python
  async def _score_and_close(self, request, response, span, span_cm, setter) -> None:
      try:
          scores = await self._score_turn(request, response)
          if scores.as_dict():
              try:
                  self._pipeline.tracer.record_scores(span, scores.as_dict())
              except Exception:
                  pass
              log.info("chat_turn_eval", request_id=response.request_id, **scores.as_dict())
          if callable(setter):
              _bind_turn_span(setter, response, scores)
      finally:
          if span_cm is not None:
              try:
                  span_cm.__exit__(None, None, None)
              except Exception:
                  pass
  ```
  The `finally` in `run` must NOT exit the span when a background task was scheduled (use a flag `handed_off`).
- [x] 2.2 Tests `tests/test_answer_query.py` (~line 1103-1160): in `test_turn_eval_records_scores_on_generated_turn` and `test_turn_eval_failure_still_answers` add `await drain_turn_evals()` after `use_case.run(...)` and before the span/evaluator assertions; add
  ```python
  @pytest.mark.asyncio
  async def test_turn_eval_does_not_delay_response(tmp_path: Path) -> None:
      class SlowEvaluator(_FakeTurnEvaluator):
          async def score(self, **kwargs):
              await asyncio.sleep(0.3)
              return await super().score(**kwargs)

      evaluator = SlowEvaluator()
      use_case, _ = _uc(tmp_path, evaluator=evaluator)
      started = time.perf_counter()
      response = await use_case.run(ChatRequest(message="Qué dice la Comunicación A 3500?"), request_id="bg")
      assert time.perf_counter() - started < 0.25
      assert response.answer
      await drain_turn_evals()
      assert evaluator.calls
  ```
  (`_FakeTurnEvaluator.score` signature: check its keyword names in the test module and mirror them.) Verify: `uv run pytest tests/test_answer_query.py -k turn_eval -q` → passes.

## 3. evals-l1 — gate

- [x] 3.1 Create `evals/gate.toml` with the `[thresholds]` table from design.md.
- [x] 3.2 Create `src/bcra_rag/evals/domain/gate.py` with `load_thresholds(path: Path) -> dict[str, float]` (tomllib; raise `ValueError` when the table is missing or a value is not a number) and `evaluate_gate(payload, thresholds, *, allow_skipped=False) -> list[str]`: for each `(name, floor)` find the owning block — `"retrieval"` if `name in payload.get("retrieval", {})` else `"generation"` if present there else report `f"{name}: missing"`; if that block's `skipped` is true → `f"{name}: {block} skipped ({block.get('skip_reason') or 'omitido'})"` unless `allow_skipped`; else `value = block[name]`; if `value is None or float(value) < floor` → `f"{name}: {value} < {floor}"`.
- [x] 3.3 `evals/run_l1.py::_parse`: add `parser.add_argument("--gate", nargs="?", const=str(Path(__file__).resolve().parent / "gate.toml"), default=None, help="Fail when a published metric is under its floor in the given TOML (default evals/gate.toml)")` and `parser.add_argument("--gate-allow-skipped", action="store_true")`. In `main()` after `asyncio.run(run_l1(...))`:
  ```python
  if args.gate:
      payload = json.loads((root / "l1.json").read_text(encoding="utf-8"))
      failures = evaluate_gate(payload, load_thresholds(Path(args.gate)), allow_skipped=args.gate_allow_skipped)
      for line in failures:
          print(f"GATE FAIL {line}")
      if failures:
          sys.exit(1)
      print("GATE OK")
  ```
- [x] 3.4 Tests `tests/evals/test_gate.py`: thresholds load from a tmp TOML; `evaluate_gate` on the committed `evals/l1.json` with `{"hit_at_5": 0.8, "citation_id_exact": 0.2}` → `[]`; with `{"mrr": 0.9}` → one line `"mrr: 0.7806 < 0.9"`; a payload whose generation block is `{"skipped": True, "skip_reason": "missing_extra"}` with `{"finding_exact": 0.1}` → one failure naming `generation skipped (missing_extra)`, and `[]` with `allow_skipped=True`; unknown metric → `"x: missing"`. Verify: `uv run pytest tests/evals/test_gate.py -q` → passes. Also `uv run python evals/run_l1.py --help` shows `--gate`.

## 4. Commands and docs sync

- [x] 4.1 `scripts/commands.toml`: after the `l1-generation` entry add
  ```toml
  [[command]]
  id = "l1-gate"
  group = "Evals"
  block = "evals"
  title = "L1 gate"
  summary = "Run L1 and fail if any published metric is under its floor in evals/gate.toml (not CI)."
  argv = ["uv", "run", "python", "evals/run_l1.py", "--gate"]
  confirm = true
  ```
- [x] 4.2 README: inside the `<!-- commands:evals -->` fence add the line `uv run python evals/run_l1.py --gate` in the same position as the catalog order; add a sentence to the Evals prose: "`--gate` compares the published metrics with the floors in `evals/gate.toml` and exits non-zero on a regression; update the floors when you publish a new `evals/l1.json`." AGENTS.md command table: add `| L1 gate | \`uv run python evals/run_l1.py --gate\` |` after "L1 generation". Verify: `uv run python scripts/devtui.py --check` → OK; `uv run pytest tests/test_devtui.py -q` → passes.
- [x] 4.3 `deploy/env.remote.example` and `.env.example`: confirm every setting introduced by changes 04, 06 and 08 is present as a commented line (`LLM_TEMPERATURE`, `LLM_MAX_TOKENS`, `LLM_SEED`, `LLM_REASONING_BUDGET`, `LLM_THINKING_USER_LAYOUT`, `CONTEXT_CHUNK_CHARS`, `RETRIEVAL_HYBRID`, `RETRIEVAL_CANDIDATES`, `RETRIEVAL_MIN_SCORE`, `INDEX_SPACE`); add any missing. `uv run pytest tests/test_deploy.py tests/test_settings.py -q` → passes.
- [x] 4.4 Sync deltas into `openspec/specs/{platform,evals-l1,query-logging}/spec.md`.

## 5. Gates

- [x] 5.1 `uv run ruff check .`; `uv run mypy src`; `uv run pytest -q --cov=src --cov-report=term-missing` → green, ≥ 80%.
- [x] 5.2 Operator check: `uv run python evals/run_l1.py --deterministic-only --gate` on the laptop prints `GATE OK` or lists the metrics under their floors (an unpublished laptop run will fail on skipped/low values — expected; the dump host is the real target).
