## Context

See proposal.md Why. Five ports stay five. Chunking, router, guardrail policy and prompts are unchanged.

Facts as of this change's writing:
- `settings.py:27-33`: `llm_api_key`, `llm_base_url`, `llm_model`, `llm_timeout_s` (default 60, ge 1), `llm_enable_thinking: bool = True`.
- `ports/llm.py`: `OnThinking = Callable[[str], Awaitable[None]]`; `LlmPort.complete(self, prompt: str, *, on_thinking: OnThinking | None = None) -> LlmDraft`.
- `adapters/llm_openai.py:151-197 LlmAdapter.complete`: builds `kwargs = {model, messages, response_format json_object, stream True, stream_options include_usage}`, `extra = _thinking_extra_body(base_url, llm_enable_thinking)` (`:216-222`, returns `None` on x.ai hosts, else `{"enable_thinking": b, "chat_template_kwargs": {"enable_thinking": b}}`), then iterates chunks through `ThinkAssembler`, calls `parse_llm_draft(raw or "{}")`, returns a copy with `thinking`, `prompt_tokens`, `completion_tokens`.
- `parse_llm_draft` (`:63-81`): `json.loads(raw)`; dict check; finding coercion; `LlmDraft.model_validate(...)` (missing `answer` → pydantic `ValidationError`, tested at `tests/test_llm_port.py:146`). `_unfence` (`:256-259`) exists but is only used for thinking display; `unwrap_thinking_text` (`:296-312`) already implements "scan `rfind('{')` backwards and `json.loads` the tail".
- `schemas.py:79-89 LlmDraft`: `answer, finding, citations, thinking, prompt_tokens, completion_tokens`.
- `use_cases/answer_query.py:433-461 generate_from_context(llm, pipeline, ctx, query, *, on_thinking, filters, timeout_s)`: `async with asyncio.timeout(timeout_s): draft = await llm.complete(prompt, on_thinking=on_thinking)`; any `Exception` → `ctx.answer = "No hay modelo disponible para completar la respuesta."`, log `step("generate", "generate", "skipped", "llm_unavailable")`, `draft=None`. `_respond` (`:336-352`) then calls `_finalize(..., abstain_reason="llm_unavailable")`. Also called from `src/bcra_rag/evals/use_cases/run_generation.py:47-53`.
- `AnswerQuery.run(request, *, request_id, on_thinking)` (`:82-128`) → `_respond(request, request_id=..., on_thinking=...)`; `api/handle.py:72-100 run_prepared_turn(..., on_thinking, turn_evaluator)`, `:103-137 handle_turn(...)`; UI `build_blocks.run_turn` (`ui/gradio_app.py:394-421`) passes `on_thinking`; `_turn` knows `staff`.
- `_respond` retrieval block (`:255-265`): `Router(self._index, manifest).route(...)` inside a `retrieve` span.
- `_log_turn` (`:609-649`) logs `guardrail_latency_ms`, `prompt_tokens`, `completion_tokens`, `**payload` (payload already includes `abstain_reason` via `response.model_dump()`).
- `RailContext` (`domain/guardrails/types.py:74-93`) is the per-turn mutable bag.
- Tests: `tests/test_llm_port.py` (`_local_settings(**kwargs)`, `StubOpenAI(content, reasoning_content=, reasoning=, chunks=)`, `client.chat.completions.kwargs[i]`), `tests/test_answer_query.py:470-485 test_llm_failure_is_silencio_not_exception_text` (uses `UnavailableLlm`), `tests/test_settings.py:41-63,87-95`.

## Goals / Non-Goals

**Goals:** bounded, configurable generation; no thinking cost for end users by default; honest failure reasons with a cheap recovery; timing fields for operators.
**Non-Goals:** changing prompts; changing rails; streaming.

## Decisions

### Decision: Generation settings (names, types, defaults, bounds)

In `Settings` after `llm_enable_thinking`:
```python
llm_temperature: float = Field(default=0.1, ge=0.0, le=2.0)
llm_max_tokens: int = Field(default=1500, ge=64)
llm_seed: int | None = None
llm_reasoning_budget: int = Field(default=0, ge=0)   # 0 = provider default
llm_thinking_user_layout: bool = False
```
Env names follow pydantic-settings: `LLM_TEMPERATURE`, `LLM_MAX_TOKENS`, `LLM_SEED`, `LLM_REASONING_BUDGET`, `LLM_THINKING_USER_LAYOUT`.

### Decision: Per-call thinking override on the port

```python
class LlmPort(Protocol):
    async def complete(
        self,
        prompt: str,
        *,
        on_thinking: OnThinking | None = None,
        thinking: bool | None = None,
    ) -> LlmDraft: ...
```
`thinking=None` means "use `llm_enable_thinking`"; `False`/`True` override for this call. `FakeLlm`, `UnavailableLlm` accept and record it (`self.thinking_args: list[bool | None]`). `LlmAdapter`: `enabled = self._settings.llm_enable_thinking if thinking is None else thinking`; `_thinking_extra_body(base_url, enabled, budget)` adds `"reasoning_budget": budget` when `budget > 0` (llama.cpp accepts it as a top-level field; x.ai hosts still get `None`). The kwargs gain `temperature`, `max_tokens`, and `seed` only when `llm_seed is not None`.

### Decision: The layout decides thinking, threaded as a plain keyword

`AnswerQuery.run(..., thinking: bool | None = None)` → `_respond(..., thinking=thinking)` → `generate_from_context(..., thinking=thinking)` → `llm.complete(prompt, on_thinking=on_thinking, thinking=thinking)`. `run_prepared_turn` and `handle_turn` gain `thinking: bool | None = None` and pass it through. UI `run_turn` passes `thinking=None if (staff or settings.llm_thinking_user_layout) else False`. HTTP `/chat` (`api/routes.py`) passes nothing (None → setting). `evals/use_cases/run_generation.py` passes nothing.

### Decision: Robust parse and typed failures

In `llm_openai.py`:
```python
class LlmBadJson(ValueError):
    """The model body is not a usable JSON draft."""


def _extract_json_object(raw: str) -> dict[str, Any]:
    text = _unfence(raw)
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        payload = None
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
`parse_llm_draft` uses `_extract_json_object`, and wraps the pydantic `ValidationError` from `LlmDraft.model_validate` in `LlmBadJson` (update `tests/test_llm_port.py:146` to expect `LlmBadJson`). In `complete`, when the stream's final `finish_reason == "length"` (read from the last chunk's `choices[0].finish_reason` if present), raise `LlmBadJson("truncated")` before parsing. `LlmBadJson` is exported from `bcra_rag.ports.llm` as well (re-export) so the use case does not import an adapter: define it in `ports/llm.py` and import it in the adapter.

In `generate_from_context`:
```python
LLM_FAILURE_COPY = {
    "llm_timeout": "El modelo tardó demasiado en responder. Probá de nuevo.",
    "llm_bad_json": "El modelo devolvió una respuesta que no se pudo leer. Probá de nuevo.",
    "llm_unavailable": "No hay modelo disponible para completar la respuesta.",
}

async def _complete_with_retry(llm, prompt, *, on_thinking, thinking, timeout_s) -> tuple[LlmDraft, str | None]:
    deadline = time.monotonic() + timeout_s
    try:
        async with asyncio.timeout(timeout_s):
            return await llm.complete(prompt, on_thinking=on_thinking, thinking=thinking), None
    except TimeoutError:
        raise LlmFailure("llm_timeout")
    except LlmBadJson:
        remaining = deadline - time.monotonic()
        if remaining <= 1.0:
            raise LlmFailure("llm_bad_json")
        try:
            async with asyncio.timeout(remaining):
                return await llm.complete(prompt, on_thinking=None, thinking=False), "retry_no_thinking"
        except TimeoutError:
            raise LlmFailure("llm_timeout")
        except LlmBadJson:
            raise LlmFailure("llm_bad_json")
    except Exception:
        raise LlmFailure("llm_unavailable")
```
where `LlmFailure(Exception)` carries `.reason`. `generate_from_context` catches `LlmFailure`, sets `ctx.answer = LLM_FAILURE_COPY[reason]`, logs `step("generate", "generate", "skipped", reason)`, stores `ctx.generate_reason = reason` (new `RailContext` field) and returns `draft=None`. `_respond` uses `abstain_reason=ctx.generate_reason or "llm_unavailable"`. The retry note is appended to the generate step detail (`"llm called (retry_no_thinking)"`).

### Decision: Timing fields

`RailContext.timings: dict[str, float] = field(default_factory=dict)`. `_respond` records `ctx.timings["retrieve_ms"]` around `Router.route`; `generate_from_context` records `ctx.timings["llm_ms"]` around the (possibly retried) completion. `LlmDraft` gains `ttft_ms: float = 0.0` and `thinking_chars: int = 0`; the adapter measures `ttft_ms` as the time from `create()` to the first chunk with any delta text and `thinking_chars = len(thinking)`. `_log_turn` adds `retrieve_ms`, `llm_ms` (rounded to 1 decimal, 0.0 when absent), `ttft_ms`, `thinking_chars`; `abstain_reason` is already in `payload`.

## Risks / Trade-offs

- [`max_tokens` too small for long TO answers] → default 1500 covers the observed 3–4k completions only when thinking is off; with thinking on, llama.cpp counts reasoning inside `max_tokens`, so operators with thinking on should raise it (documented in README).
- [`reasoning_budget` unknown to a provider] → sent only when > 0; documented as llama.cpp-specific.
- [Retry doubles cost on bad JSON] → bounded by the same wall-clock timeout; thinking off makes the retry short.

## Migration Plan

Additive settings with safe defaults; deploy normally. Rollback: revert.

## Open Questions

None.
