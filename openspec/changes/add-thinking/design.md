## Context

See proposal.md Why and the delta specs under `specs/` for the `thinking` field, the output-box contract, and the log exclusion.

Product runtime already exists. Unchanged architecture (restated so this design satisfies the constitution):

- **Ports:** Catalog, Extractor, Index (owns embeddings), Llm, SessionStore. This change does not add a port. `LlmPort.complete(prompt, *, on_thinking=None) -> LlmDraft` stays the only language-model method.
- **Composition:** `build_ingest` / `build_app`; no DI container. `LlmAdapter` when `LLM_API_KEY` is set, else `UnavailableLlm`. `create_fastapi` still builds Blocks and calls `mount_ui`.
- **Ingest/refresh pipeline:** catalog → polite fetch → classify → extract → chunk A/B → index upsert → MANIFEST checkpoint. Untouched.
- **Router / chunking / session:** aliases; named Com. A `get_section` vs vigente (TO ∪ later A’s); serving uses structured chunker B on TO + clean A’s and fixed A otherwise; in-process session (last six messages), one worker, `/clear`. Session still stores `(user, answer)` only.
- **Host-side refresh:** systemd oneshots + cron.d on the dump host (not GitHub Actions).

Constraints: Python 3.11+ via uv; pydantic v2; FastAPI; Gradio **6.x** mounted on FastAPI at `/`. Chat Completions via the OpenAI SDK against `LLM_BASE_URL` (default `https://api.x.ai/v1`; local llama.cpp is the same adapter). `response_format={"type": "json_object"}`. Observatory CSS is hatch force-included. `[data-testid="status-tracker"]` is hidden, so the chat stage has no loading chrome today.

## Goals / Non-Goals

**Goals:**

- Capture a provider reasoning trace onto `LlmDraft.thinking` / `ChatResponse.thinking` without changing the JSON answer schema.
- Show it in `#observatory-chat` as a Gradio thought (`.thought-group`), distinct from the answer bubble, in the Staff (IA) layout only (`#observatory-shell.layout-user` hides it), with the trace text filling in as Chat Completions deltas arrive.
- Same path for hosted xAI and local Qwen3.6-35B-A3B on llama.cpp `llama-server`.
- Unit tests; `src` coverage >= 80%.

**Non-Goals (design-level):**

- `LlmPort.stream`, HTTP SSE, streaming the cited JSON into the answer bubble. Observatory thinking deltas stay in `complete(..., on_thinking=)`.
- A second adapter, `xai_sdk`, Responses API, `reasoning_effort`, bundling llama.cpp, changing default `LLM_MODEL`.
- Observatory thinking toggle; replaying thinking into `SessionStore` or Qwen `preserve_thinking` from the app.
- New port, Next.js, LlamaIndex, Redis, Banxico, 1990–97 hole, GitHub-hosted vector index.
- Package version bump.

## Decisions

### Decision: thinking on `LlmDraft` / `ChatResponse`, not a new port

`LlmDraft.thinking: str = ""`. `ChatResponse.thinking: str | None = None` (`extra=forbid` otherwise). `ChatRequest` still rejects `thinking`. `AnswerQuery` copies `draft.thinking` onto the response only after `complete()` succeeds. Clear / block / empty-hits / `index_not_ready` / `llm_unavailable` leave it unset.

`parse_llm_draft` still validates `answer`, `finding`, `citations` only. A JSON key `thinking` inside the model body is ignored (the cited-answer schema is not a CoT channel).

Alternatives: new `stream()` on `LlmPort` (splits the graph); UI-only field not on HTTP (Gradio still goes through `handle_turn` → `ChatResponse`).

### Decision: extract three sources, no model allowlist

`LlmAdapter.complete` always sends `stream=True` (HTTP still waits for the finished `LlmDraft`). An incremental assembler reads each chunk:

1. String `delta.reasoning_content` (xAI, llama.cpp `--reasoning-format auto|deepseek`)
2. Else string `delta.reasoning`
3. Else, if this call has not seen extras, a tag state machine on `delta.content`: inner text of `<think>` / `<thinking>` is thinking; text outside is the JSON body. Hold a short suffix that could be an incomplete tag. If extras were seen, all `content` is JSON.

After the stream, `json.loads` the JSON buffer (`answer` / `finding` / `citations` only). If the JSON payload is a substring of thinking (or a trailing object with an `answer` key), strip it from thinking. Do not strip `draft.answer` prose.

When `on_thinking` is set, await it with the accumulated trace whenever the thinking channel grows. Never pass JSON-buffer text to the callback.

OpenAI SDK types use `extra="allow"`, so extras survive. Do not key off `LLM_MODEL`.

### Decision: `LLM_ENABLE_THINKING` defaults on

`Settings.llm_enable_thinking: bool = True`. Local OpenAI-compatible servers (llama.cpp / Qwen) get `extra_body={"enable_thinking": <bool>, "chat_template_kwargs": {"enable_thinking": <bool>}}`. `api.x.ai` never gets that extra body (native thinking; unknown kwargs can 400). Set `false` to turn llama.cpp thinking off.

Do not send `preserve_thinking` from the app. Dummy `LLM_API_KEY` for local llama.cpp stays required (`UnavailableLlm` when empty). Operators who need long local traces raise `LLM_TIMEOUT_S`; do not change the 60s default.

### Decision: live thought yields via `on_thinking`, not `LlmPort.stream`

`complete` stays the only port method. Optional `on_thinking: Callable[[str], Awaitable[None]] | None = None` on every implementation. HTTP omits it. Gradio passes a latest-wins slot (`list` + `asyncio.Event`): the callback writes the newest accumulated string and sets the event; the generator waits, yields, clears the event. Tokens that arrive during a yield collapse to one UI update. No unbounded queue of prefixes. Cancel the `handle_turn` task if the generator exits early so `_remember` does not run after Clear.

The observatory generator is module-level (not a nested Blocks closure) so tests can drive it with `FakeLlm(think_chunks=...)`.

1. Snapshot history. Yield user + pending thought (`Pensando…`, `status=pending`, empty body). `gr.skip()` inspector.
2. `create_task(handle_turn(..., on_thinking=...))`. On each event with a non-empty slot, yield the same pending thought with `content=accumulated` (still no answer row).
3. Final: 401/429 → Spanish notice, no thought. `ChatResponse` with a trace → collapse prior thoughts (`status=done` on copied metadata), latest thought **omits** `status` (Gradio: missing status => accordion open, collapsible) with title `Pensó Ns` and `duration`, then a separate answer row. No trace → answer only. Failed generate with empty thinking drops the live thought.

`gr.Chatbot(..., group_consecutive_messages=False)` so the thought and the cited answer are not one `.bot` bubble. Do not set `parent_id` or `reasoning_tags`.

Gradio 6 thought wrapper is `.thought-group`. Observatory CSS mutes that chrome and the bot wrapper that `:has(.thought-group)`, and caps `.thought-group .content` height. Do not restyle `.assistant.message` / `.bot.message` globally. Do not hardcode hashed `svelte-*` classes. Status tracker stays hidden.

Alternatives: `LlmPort.stream` (splits the graph); HTTP SSE (out of spec); `status=done` on the latest thought (hides the trace).

### Decision: do not replay or log the trace

`_remember(session_id, user, response.answer)` unchanged. Next OpenAI `messages` stay system + this-turn user prompt. `_log_turn` pops `thinking` before `model_dump` lands on console / `chat.log`.

### Decision: IBM 1–4 take/leave (unchanged)

| Take | Leave |
|---|---|
| Prompt template with last_refresh / to_as_of; structured JSON; FastAPI not Flask | Flask; model bake-off |
| RAG loop; Gradio | LlamaIndex; LangGraph agent |
| Chroma + metadata filters; upsert on refresh | Recommender |
| Vector search; parent doc = get_section; self-query ≈ regex+filters; HNSW default | FAISS second index; multi-query unless L1 citation-id is poor |

### Decision: slip order (unchanged)

1. Deontic retry (not a v1 spec MUST) 2. HTTP SSE / streaming the JSON answer bubble — still slipped; this change streams thinking deltas in the observatory only 3. Chunking B on A-series (keep B on TO) 4. Gold cap 30 5. Coverage gate is src >= 80%. Never cut: TO + post-TO ingest, resume+refresh CLI, last_refresh banner, cite-or-abstain, citation-id, unit tests, uv/ruff/mypy/pytest --cov, health HTTP 200 on empty index, polite download.

Deontic scan stays slip-first in design only.

## Risks / Trade-offs

- [Empty `reasoning_content` on some SKUs] → pending motion still runs; final yield drops the thought if `thinking` is empty.
- [llama.cpp `--reasoning-format none` leaves `<think>` in content] → strip tags before `parse_llm_draft`. Document `--reasoning-format auto`.
- [JSON grammar from token 0 swallows `<think>`] → keep `json_object`. Do not add `LLM_JSON_OBJECT` unless apply proves it. Prefer llama.cpp auto/deepseek format so the server splits the trace from the JSON body.
- [xAI 400 on `chat_template_kwargs`] → never send extra_body to `api.x.ai`; still extract `reasoning_content`.
- [Local traces vs `llm_timeout_s=60`] → document a higher `LLM_TIMEOUT_S`; do not change the default.
- [Pending flash on silencio without LLM] → accept; final yield MUST drop the empty region.
- [Hashed Gradio svelte classes] → style `.thought-group` only.
- [Thought CSS leaks onto the answer bubble] → `group_consecutive_messages=False`; mute `#observatory-chat .bot:has(.thought-group)`; style `.thought-group` only.
- [JSON tokens in the thought] → never copy the JSON buffer onto `on_thinking`; split-tag and JSON-only stream tests.
- [`json_object` + `stream=True` 400] → keep json_object; prefer llama.cpp `--reasoning-format auto`. Do not dump JSON into the thought.
- [Latest thought `status=done` hides the trace] → omit `status` on the latest completed thought; priors get `status=done`.
- [Unbounded thinking queue] → latest-wins slot + Event.
- [Generator exit leaves `_remember` running] → cancel the `handle_turn` task.

## Migration Plan

No dump or index migration. Deploy is a normal API restart. Rollback is revert; `POST /chat` without `thinking` is the old shape plus an optional field clients may ignore. Operators pointing `LLM_*` at llama.cpp keep a dummy key; thinking extra_body is on by default (`LLM_ENABLE_THINKING=true`) and a longer timeout may be needed. README Debug names the default-on thinking vars; `.env.example` sets `LLM_ENABLE_THINKING=true`.
