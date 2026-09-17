## Why

Cited CAMEX clauses with visible guardrails and L1 numbers. The language-model call is not tunable and its failures are lumped together. `LlmAdapter.complete` (`src/bcra_rag/adapters/llm_openai.py:151-197`) sends no `temperature`, `max_tokens`, `seed` or reasoning budget — only a global `LLM_ENABLE_THINKING` boolean — so the local thinking model spends 75 s (p50) to 138 s (p95) per answer and 3–4k completion tokens on a 1.2k-token prompt, and end users in the Usuario layout wait through thinking they never see. `parse_llm_draft` (`:63-81`) is a bare `json.loads`: a fenced or prose-wrapped JSON body raises, and that error shares the `except Exception` branch with a timeout (`use_cases/answer_query.py:450-461`), so both surface as "No hay modelo disponible para completar la respuesta." with `abstain_reason=llm_unavailable`, hiding the real cause. The `chat_turn` log (`:609-649`) has no model wall time, time to first token, thinking size, or retrieval time.

## What Changes

- New settings `LLM_TEMPERATURE` (0.1), `LLM_MAX_TOKENS` (1500), `LLM_SEED` (unset), `LLM_REASONING_BUDGET` (0 = provider default) and `LLM_THINKING_USER_LAYOUT` (false) SHALL control the call; the `LlmPort.complete` contract gains an optional per-call `thinking` override, and turns from the end-user layout SHALL run with thinking off unless `LLM_THINKING_USER_LAYOUT` is true.
- The model body SHALL be parsed after stripping a code fence and, failing that, from the last balanced JSON object in the text. Parse failures SHALL be reported as `abstain_reason` `llm_bad_json` after one retry with thinking off; timeouts as `llm_timeout`; other failures keep `llm_unavailable`. Each reason SHALL have its own Spanish answer.
- The `chat_turn` record SHALL include `retrieve_ms`, `llm_ms`, `ttft_ms`, `thinking_chars` and `abstain_reason`.

## Capabilities

### New Capabilities

- (none)

### Modified Capabilities

- `platform`: language-model generation settings; timeout reason.
- `query-answering`: language-model call failure reasons; end-user layout does not pay for thinking.
- `query-logging`: timing and reasoning fields on the chat turn.

## Non-goals

- Banxico or any non-`bcra.gob.ar` corpus.
- Next.js v1.
- LlamaIndex.
- Redis.
- Filling the 1990–97 CAMEX catalog hole.
- GitHub-hosted vector index.
- Changing the prompt language or content (change 05).
- Streaming the final answer (rails run after generation).
- A sixth port: `thinking` is an optional keyword on the existing `LlmPort.complete`.

## Impact

- `src/bcra_rag/settings.py`, `src/bcra_rag/ports/llm.py`, `src/bcra_rag/adapters/llm_openai.py`, `src/bcra_rag/adapters/llm_fake.py`, `src/bcra_rag/schemas.py` (`LlmDraft.ttft_ms`, `thinking_chars`), `src/bcra_rag/use_cases/answer_query.py`, `src/bcra_rag/api/handle.py`, `src/bcra_rag/ui/gradio_app.py`, `src/bcra_rag/domain/guardrails/types.py` (`RailContext.timings`).
- Callers that must keep working unchanged: `src/bcra_rag/evals/use_cases/run_generation.py` (`generate_from_context`), `tests/test_ui.py` fake `run_turn`s, `tests/test_llm_port.py::StubOpenAI`.
- README Debug paragraph names the new variables; `.env.example` and `deploy/env.remote.example` gain them commented. No command change.
