# Tasks — 04 LLM generation settings and parsing

Requires change 01. Line anchors are as of this change's writing; grep the quoted symbol if they moved. Keep every new parameter optional with a default so `src/bcra_rag/evals/use_cases/run_generation.py` and the UI test fakes keep working.

## 1. platform — settings

- [ ] 1.1 `src/bcra_rag/settings.py`, after `llm_enable_thinking: bool = True` (~line 32), add:
  ```python
  llm_temperature: float = Field(default=0.1, ge=0.0, le=2.0)
  llm_max_tokens: int = Field(default=1500, ge=64)
  llm_seed: int | None = None
  llm_reasoning_budget: int = Field(default=0, ge=0)
  llm_thinking_user_layout: bool = False
  ```
- [ ] 1.2 `tests/test_settings.py::test_chat_settings_defaults` (~line 41): add `monkeypatch.delenv` for `LLM_TEMPERATURE`, `LLM_MAX_TOKENS`, `LLM_SEED`, `LLM_REASONING_BUDGET`, `LLM_THINKING_USER_LAYOUT` (raising=False) and assert `settings.llm_temperature == 0.1`, `settings.llm_max_tokens == 1500`, `settings.llm_seed is None`, `settings.llm_reasoning_budget == 0`, `settings.llm_thinking_user_layout is False`. Add `test_llm_generation_settings_from_env` setting the five env vars (`"0.7"`, `"800"`, `"7"`, `"512"`, `"true"`) and asserting the parsed values. Verify: `uv run pytest tests/test_settings.py -q` → passes.

## 2. platform — port and adapters

- [ ] 2.1 `src/bcra_rag/ports/llm.py`: add
  ```python
  class LlmBadJson(ValueError):
      """The model body is not a usable JSON answer object."""
  ```
  and extend the protocol to
  ```python
  async def complete(
      self,
      prompt: str,
      *,
      on_thinking: OnThinking | None = None,
      thinking: bool | None = None,
  ) -> LlmDraft: ...
  ```
- [ ] 2.2 `src/bcra_rag/schemas.py::LlmDraft` (~line 79-89): add `ttft_ms: float = 0.0` and `thinking_chars: int = 0` after `completion_tokens`.
- [ ] 2.3 `src/bcra_rag/adapters/llm_fake.py`: `FakeLlm.__init__` adds `self.thinking_args: list[bool | None] = []`; both `FakeLlm.complete` and `UnavailableLlm.complete` accept `thinking: bool | None = None` and append it to `self.thinking_args` (UnavailableLlm gets the same list attribute). Also give `FakeLlm` an optional constructor kwarg `fail_first: type[Exception] | None = None` — when set, the first `complete` call records `thinking` in `self.thinking_args`, then raises `fail_first("bad")` and clears the flag, so a retry sees `thinking_args == [None, False]` (used by the retry test).
- [ ] 2.4 `src/bcra_rag/adapters/llm_openai.py`:
  - import `LlmBadJson` from `bcra_rag.ports.llm`.
  - Replace `parse_llm_draft` body (~line 63-81): call `payload = _extract_json_object(raw)` (new helper below), keep the finding coercion, wrap `LlmDraft.model_validate(...)` in `try/except ValidationError as exc: raise LlmBadJson(str(exc)) from exc` (`from pydantic import ValidationError`).
  - Add:
    ```python
    def _extract_json_object(raw: str) -> dict[str, Any]:
        text = _unfence(raw)
        payload: Any = None
        try:
            payload = json.loads(text)
        except json.JSONDecodeError:
            start = text.rfind("{")
            while start != -1:
                try:
                    payload = json.loads(text[start:])
                    break
                except json.JSONDecodeError:
                    start = text.rfind("{", 0, start)
        if not isinstance(payload, dict):
            raise LlmBadJson("LLM draft is not a JSON object")
        return payload
    ```
  - `_thinking_extra_body(base_url: str, enabled: bool, budget: int = 0)` (~line 216): when `budget > 0` add `"reasoning_budget": budget` to the returned dict.
  - `LlmAdapter.complete(self, prompt, *, on_thinking=None, thinking: bool | None = None)` (~line 151): `enabled = self._settings.llm_enable_thinking if thinking is None else thinking`; kwargs gain `"temperature": self._settings.llm_temperature`, `"max_tokens": self._settings.llm_max_tokens`, and `"seed": self._settings.llm_seed` only when not `None`; `extra = _thinking_extra_body(base_url, enabled, self._settings.llm_reasoning_budget)`. Measure `started = time.perf_counter()` before `create()`, set `ttft_ms` at the first chunk where `assembler.feed_chunk(chunk)` returns true (`ttft_ms = (time.perf_counter() - started) * 1000` once). Track `finish_reason`: for each chunk, `choices = getattr(chunk, "choices", None) or []`; if `choices` and `getattr(choices[0], "finish_reason", None) == "length"` set `truncated = True`. After the loop, if `truncated` raise `LlmBadJson("truncated")`. Return `draft.model_copy(update={..., "ttft_ms": round(ttft_ms, 1), "thinking_chars": len(thinking)})`.
- [ ] 2.5 Tests in `tests/test_llm_port.py`:
  - `test_parse_llm_draft_missing_answer_fails` (~line 146): expect `LlmBadJson` instead of `ValidationError`.
  - Add:
    ```python
    def test_parse_llm_draft_strips_fence() -> None:
        body = "```json\n" + _cited_json() + "\n```"
        assert parse_llm_draft(body).finding is not None


    def test_parse_llm_draft_uses_last_object_after_prose() -> None:
        body = "Aquí va la respuesta: " + _cited_json()
        draft = parse_llm_draft(body)
        assert draft.citations


    def test_parse_llm_draft_prose_only_is_bad_json() -> None:
        with pytest.raises(LlmBadJson):
            parse_llm_draft("no puedo responder")


    @pytest.mark.asyncio
    async def test_adapter_sends_generation_settings() -> None:
        client = StubOpenAI(_cited_json())
        llm = LlmAdapter(_local_settings(llm_seed=7, llm_reasoning_budget=512), client=client)
        await llm.complete("pregunta")
        kwargs = client.chat.completions.kwargs[0]
        assert kwargs["temperature"] == 0.1
        assert kwargs["max_tokens"] == 1500
        assert kwargs["seed"] == 7
        assert kwargs["extra_body"]["reasoning_budget"] == 512


    @pytest.mark.asyncio
    async def test_adapter_default_has_no_seed_or_budget() -> None:
        client = StubOpenAI(_cited_json())
        await LlmAdapter(_local_settings(), client=client).complete("pregunta")
        kwargs = client.chat.completions.kwargs[0]
        assert "seed" not in kwargs
        assert "reasoning_budget" not in kwargs["extra_body"]


    @pytest.mark.asyncio
    async def test_adapter_thinking_override_beats_setting() -> None:
        client = StubOpenAI(_cited_json())
        await LlmAdapter(_local_settings(), client=client).complete("pregunta", thinking=False)
        assert client.chat.completions.kwargs[0]["extra_body"]["enable_thinking"] is False


    @pytest.mark.asyncio
    async def test_adapter_reports_ttft_and_thinking_chars() -> None:
        client = StubOpenAI(_cited_json(), reasoning_content="pienso")
        draft = await LlmAdapter(_local_settings(), client=client).complete("pregunta")
        assert draft.thinking_chars == len("pienso")
        assert draft.ttft_ms >= 0.0
    ```
    Add a `finish_reason` attribute to `_StreamChoice` (`self.finish_reason = finish_reason` with default `None`) and a test that a final chunk with `finish_reason="length"` makes `complete` raise `LlmBadJson`.
  Verify: `uv run pytest tests/test_llm_port.py -q` → passes.

## 3. query-answering — typed failures, retry, timings

- [ ] 3.1 `src/bcra_rag/domain/guardrails/types.py::RailContext` (~line 74-93): add `timings: dict[str, float] = field(default_factory=dict)` and `generate_reason: str | None = None`.
- [ ] 3.2 `src/bcra_rag/use_cases/answer_query.py`:
  - imports: `import time` (if absent), `from bcra_rag.ports.llm import LlmBadJson, LlmPort, OnThinking`.
  - Add near `GeneratedFromContext`:
    ```python
    LLM_FAILURE_COPY: dict[str, str] = {
        "llm_timeout": "El modelo tardó demasiado en responder. Probá de nuevo.",
        "llm_bad_json": "El modelo devolvió una respuesta que no se pudo leer. Probá de nuevo.",
        "llm_unavailable": "No hay modelo disponible para completar la respuesta.",
    }


    class LlmFailure(Exception):
        def __init__(self, reason: str) -> None:
            super().__init__(reason)
            self.reason = reason


    async def _complete_with_retry(
        llm: LlmPort,
        prompt: str,
        *,
        on_thinking: OnThinking | None,
        thinking: bool | None,
        timeout_s: float,
    ) -> tuple[LlmDraft, str | None]:
        deadline = time.monotonic() + timeout_s
        try:
            async with asyncio.timeout(timeout_s):
                return await llm.complete(prompt, on_thinking=on_thinking, thinking=thinking), None
        except TimeoutError as exc:
            raise LlmFailure("llm_timeout") from exc
        except LlmBadJson:
            remaining = deadline - time.monotonic()
            if remaining <= 1.0:
                raise LlmFailure("llm_bad_json") from None
            try:
                async with asyncio.timeout(remaining):
                    draft = await llm.complete(prompt, on_thinking=None, thinking=False)
                return draft, "retry_no_thinking"
            except TimeoutError as exc:
                raise LlmFailure("llm_timeout") from exc
            except LlmBadJson as exc:
                raise LlmFailure("llm_bad_json") from exc
        except Exception as exc:
            raise LlmFailure("llm_unavailable") from exc
    ```
  - `generate_from_context` (~line 433): add keyword `thinking: bool | None = None`; replace the `try: async with asyncio.timeout(...) ... except Exception:` block with
    ```python
    started = time.perf_counter()
    try:
        draft, retry_note = await _complete_with_retry(
            llm, prompt, on_thinking=on_thinking, thinking=thinking, timeout_s=timeout_s
        )
    except LlmFailure as failure:
        ctx.timings["llm_ms"] = (time.perf_counter() - started) * 1000
        ctx.generate_reason = failure.reason
        ctx.finding = Finding.SILENCIO
        ctx.answer = LLM_FAILURE_COPY[failure.reason]
        rest = [step("generate", "generate", "skipped", failure.reason)]
        return GeneratedFromContext(log=rest, output_log=[], draft=None, blocked=None)
    ctx.timings["llm_ms"] = (time.perf_counter() - started) * 1000
    try:
        pipeline.tracer.record_tokens(draft.prompt_tokens, draft.completion_tokens)
    except Exception:
        pass
    detail = "llm called" if retry_note is None else f"llm called ({retry_note})"
    generate_log = [step("generate", "generate", "pass", detail)]
    ```
  - `AnswerQuery.run` and `_respond`: add `thinking: bool | None = None` keyword, pass to `generate_from_context(..., thinking=thinking)`; in `_respond` change `abstain_reason="llm_unavailable"` (~line 351) to `abstain_reason=ctx.generate_reason or "llm_unavailable"`.
  - `_respond` retrieval (~line 255-265): wrap the `Router(...).route(...)` call with `t0 = time.perf_counter()` … `ctx.timings["retrieve_ms"] = (time.perf_counter() - t0) * 1000` (set it in both the success path and before re-raising).
  - `_log_turn` (~line 609-649): add fields
    ```python
    retrieve_ms=round(ctx.timings.get("retrieve_ms", 0.0), 1),
    llm_ms=round(ctx.timings.get("llm_ms", 0.0), 1),
    ttft_ms=round(getattr(ctx.draft, "ttft_ms", 0.0), 1) if ctx.draft else 0.0,
    thinking_chars=getattr(ctx.draft, "thinking_chars", 0) if ctx.draft else 0,
    ```
    (`abstain_reason` is already present through `**payload`; do not add it twice).
- [ ] 3.3 `src/bcra_rag/api/handle.py`: `run_prepared_turn(..., on_thinking=None, turn_evaluator=None, thinking: bool | None = None)` passes `thinking=thinking` to `use_case.run`; `handle_turn` gains `thinking: bool | None = None` and forwards it.
- [ ] 3.4 `src/bcra_rag/ui/config.py`: add
  ```python
  def thinking_for_layout(staff: bool, settings: Settings) -> bool | None:
      """None keeps LLM_ENABLE_THINKING; False turns thinking off for a Usuario turn."""
      if staff or settings.llm_thinking_user_layout:
          return None
      return False
  ```
  (`from bcra_rag.settings import Settings`; check the module does not already import it under TYPE_CHECKING). `src/bcra_rag/ui/gradio_app.py::build_blocks._turn.run_turn` (~line 394-421): pass `thinking=thinking_for_layout(staff, settings)` to `handle_turn`.
- [ ] 3.5 Tests:
  - `tests/test_answer_query.py`: keep `test_llm_failure_is_silencio_not_exception_text` (`UnavailableLlm` → `llm_unavailable`, answer still names `last_refresh`). Add:
    ```python
    @pytest.mark.asyncio
    async def test_llm_timeout_reason(tmp_path: Path) -> None:
        class SlowLlm(FakeLlm):
            async def complete(self, prompt, *, on_thinking=None, thinking=None):
                await asyncio.sleep(0.2)
                return await super().complete(prompt, on_thinking=on_thinking, thinking=thinking)

        settings, index, _ = seed_ready(tmp_path)
        settings = settings.model_copy(update={"llm_timeout_s": 0.05})
        use_case = AnswerQuery(settings, index, SlowLlm(IN_CORPUS_DRAFT), InMemorySessionStore(), default_pipeline(settings))
        response = await use_case.run(ChatRequest(message="Qué dice la Comunicación A 3500?"), request_id="t")
        assert response.abstain_reason == "llm_timeout"
        assert "tardó demasiado" in response.answer


    @pytest.mark.asyncio
    async def test_llm_bad_json_retries_without_thinking(tmp_path: Path) -> None:
        settings, index, _ = seed_ready(tmp_path)
        llm = FakeLlm(IN_CORPUS_DRAFT, fail_first=LlmBadJson)
        use_case = AnswerQuery(settings, index, llm, InMemorySessionStore(), default_pipeline(settings))
        response = await use_case.run(ChatRequest(message="Qué dice la Comunicación A 3500?"), request_id="r")
        assert llm.thinking_args == [None, False]
        assert response.finding is not Finding.SILENCIO or response.abstain_reason != "llm_bad_json"
        assert any(g.rule == "generate" and "retry_no_thinking" in (g.detail or "") for g in response.guardrails)


    @pytest.mark.asyncio
    async def test_llm_bad_json_twice(tmp_path: Path) -> None:
        class BadLlm(FakeLlm):
            async def complete(self, prompt, *, on_thinking=None, thinking=None):
                self.thinking_args.append(thinking)
                raise LlmBadJson("bad")

        settings, index, _ = seed_ready(tmp_path)
        use_case = AnswerQuery(settings, index, BadLlm(), InMemorySessionStore(), default_pipeline(settings))
        response = await use_case.run(ChatRequest(message="Qué dice la Comunicación A 3500?"), request_id="b")
        assert response.abstain_reason == "llm_bad_json"
        assert "no se pudo leer" in response.answer


    @pytest.mark.asyncio
    async def test_thinking_flag_reaches_llm(tmp_path: Path) -> None:
        settings, index, _ = seed_ready(tmp_path)
        llm = FakeLlm(IN_CORPUS_DRAFT)
        use_case = AnswerQuery(settings, index, llm, InMemorySessionStore(), default_pipeline(settings))
        await use_case.run(ChatRequest(message="Qué dice la Comunicación A 3500?"), request_id="u", thinking=False)
        assert llm.thinking_args == [False]
    ```
    (`import asyncio`, `from bcra_rag.ports.llm import LlmBadJson`, `from bcra_rag.adapters.llm_fake import FakeLlm` as needed.)
  - `tests/test_ui.py`: add `test_thinking_for_layout` asserting `thinking_for_layout(False, Settings(data_dir=tmp_path)) is False`, `thinking_for_layout(True, Settings(data_dir=tmp_path)) is None`, and `thinking_for_layout(False, Settings(data_dir=tmp_path, llm_thinking_user_layout=True)) is None`.
  - Log fields: in `tests/test_answer_query.py` find the existing `chat_turn` log capture test (search `"chat_turn"`; if it uses `structlog.testing.capture_logs`, extend it) and assert the keys `retrieve_ms`, `llm_ms`, `ttft_ms`, `thinking_chars` are present.
  Verify: `uv run pytest tests/test_answer_query.py tests/test_ui.py tests/test_chat_api.py -q` → passes.

## 4. Docs

- [ ] 4.1 README `### Debug` paragraph (~line 129): after the `LLM_ENABLE_THINKING` sentences add: "`LLM_TEMPERATURE` (0.1), `LLM_MAX_TOKENS` (1500; with thinking on, llama.cpp counts reasoning tokens inside this bound — raise it or set `LLM_REASONING_BUDGET`), `LLM_SEED` (unset), `LLM_REASONING_BUDGET` (0 = provider default; llama.cpp only), `LLM_THINKING_USER_LAYOUT` (false: Usuario turns run without thinking). A timed-out call is `abstain_reason=llm_timeout`; an unreadable body retries once without thinking, then `llm_bad_json`. `chat_turn` logs `retrieve_ms`, `llm_ms`, `ttft_ms`, `thinking_chars`."
- [ ] 4.2 `.env.example` and `deploy/env.remote.example`: after `LLM_ENABLE_THINKING=true` add commented lines `# LLM_TEMPERATURE=0.1`, `# LLM_MAX_TOKENS=1500`, `# LLM_SEED=`, `# LLM_REASONING_BUDGET=0`, `# LLM_THINKING_USER_LAYOUT=false`. Verify: `uv run pytest tests/test_settings.py tests/test_deploy.py -q` → passes.
- [ ] 4.3 Sync spec deltas into `openspec/specs/{platform,query-answering,query-logging}/spec.md`.

## 5. Gates

- [ ] 5.1 `uv run ruff check .`; `uv run mypy src`; `uv run pytest -q --cov=src --cov-report=term-missing` → green, ≥ 80%.
- [ ] 5.2 Operator check against local llama.cpp: a Usuario turn shows no "Pensó" row and returns markedly faster than a Staff turn; `data/logs/chat.log` last line has `llm_ms`, `ttft_ms`, `thinking_chars`.
