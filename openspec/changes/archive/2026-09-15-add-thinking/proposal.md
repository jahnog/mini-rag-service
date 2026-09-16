## Why

Cited CAMEX clauses with visible guardrails and L1 numbers. Reasoning-capable language models already return a separate thinking trace before that clause, but the observatory waits on a single completion and then shows only the JSON answer — with the status tracker hidden, the output box stays frozen — so staff and end users cannot tell the model is working or inspect how it reached the citation.

## What Changes

Nothing is **BREAKING**. `POST /chat` gains an optional `thinking` field on the response (absent, null, or empty when the provider returns no trace). The request contract is unchanged.

- Capture a provider reasoning trace when the language model is called and the provider exposes one (xAI-style extras or think-tags around the JSON body), without mixing it into `answer` or `Fuente:`.
- Show that trace in the chat output box, visually distinct from the cited answer, in the Staff (IA) layout only. The thinking region is not shown in Usuario. The thinking region shows the provider trace text as it is received, not only a title/label. The cited answer / `Fuente:` / silencio text MUST NOT appear inside the thinking region.
- While a turn is in flight, the thinking region in the output box moves (spinner and/or pulse) and shows the trace as the provider sends it, before the cited answer appears.
- When the provider returns no trace — including paths that never call the model — do not leave an empty thinking region.
- Session memory still stores the cited answer, not the trace. Chat-turn logs still omit the trace (same exclusion as the language-model prompt).
- Thinking is on by default (`LLM_ENABLE_THINKING=true`). Local OpenAI-compatible servers (including Qwen3.6-35B-A3B on llama.cpp) receive `enable_thinking` extra body; `api.x.ai` does not. Set `false` to disable llama.cpp thinking.
- README `## How to run` Debug names that local Qwen thinking uses existing `LLM_*` (no new operator command).

## Capabilities

### New Capabilities

- None.

### Modified Capabilities

- `query-answering`: optional `thinking` on the structured chat response when the language-model provider returns a reasoning trace; answer and session memory stay the cited clause; no invented trace when the model is not called.
- `assistant-ui`: thinking region in the chat output box, distinct from the answer, showing the trace as it is received while the turn is in flight, in the staff layout only; Clear still drops it.
- `query-logging`: chat-turn records MUST NOT persist the thinking trace.

## Non-goals

- Banxico or any non-`bcra.gob.ar` corpus.
- Next.js v1.
- LlamaIndex.
- Redis.
- Filling the 1990–97 CAMEX catalog hole.
- GitHub-hosted vector index.
- HTTP `POST /chat/stream` or SSE. No streaming of the cited JSON answer into the answer bubble. Observatory thinking deltas (the provider trace as it is received) are in scope.
- A thinking on/off control in the observatory.
- Bundling llama.cpp or changing the default `LLM_MODEL`.
- xAI Responses API, a second language-model adapter, or a `reasoning_effort` setting.
- Replaying thinking into session memory or Qwen `preserve_thinking` from the app.
- Logging the thinking trace or the language-model prompt.
- A git-flow version bump.

## Impact

- Language-model adapter streams Chat Completions inside `complete`, reads reasoning extras (and think-tags in content) as they arrive, and sends `enable_thinking` extra body by default on non-xAI bases. `LlmDraft` / `ChatResponse` gain optional `thinking`. AnswerQuery copies it only after generate. An optional `on_thinking` callback lets the observatory show the trace as it is received. `POST /chat` stays one shot.
- Gradio chat turn is a generator: pending thought that fills with the live trace, then the expanded collapsible trace in its own region plus a separate cited-answer bubble (or drop the pending region when there is no trace). Observatory CSS distinguishes thought chrome from the answer bubble.
- Unit tests for extract/parse, extra-body gating, generate vs silencio paths, log stripping, message shape, and CSS tokens. `src` coverage stays >= 80%.
- No new Python dependencies. Five ports stay; `LlmPort.complete` stays. Ingest/refresh, router, and `POST /chat` request body are unchanged.
- README `## How to run` Debug adds one line (no new command fence). `.env.example` sets `LLM_ENABLE_THINKING=true`.
