# Removal ledger

Features considered for removal or simplification. The cited clause or silencio, on an index built with `auto`, `openai`, or `deterministic` embeddings, is the result this list is about.

## Keep

### Offline L1

`src/bcra_rag/evals/`, `evals/`, `GET /l1`, and the Calidad L1 accordion.

Required differentiator. Chat does not use the score to write the answer.

### Email one-time-code login

`src/bcra_rag/auth/` and the sign-in card.

Required to prevent abuse. It runs before `AnswerQuery` and only namespaces the session id.

### Staff citation inspector and trust panel

The side column in `src/bcra_rag/ui/gradio_app.py`: citation card, copy-id, and the trust log.

Required differentiator. It redraws fields the chat response already has.

### Per-IP rate limit and daily turn caps

`src/bcra_rag/api/rate_limit.py` and `src/bcra_rag/api/turn_caps.py`.

Same abuse gate as login. A request that is allowed still gets the same answer.

### Dev command TUI

`scripts/devtui.py`, `scripts/commands.toml`, `run.sh`, and the `<!-- commands:… -->` README blocks it syncs.

Developer convenience. It never runs inside the service and adds nothing to ingest, retrieve, cite, or silencio.

### Suggested-prompt buttons

The four canned examples in `src/bcra_rag/ui/config.py` and their buttons in `src/bcra_rag/ui/gradio_app.py`.

Keep by explicit decision. Clicking an example fills the question input without submitting a turn; the examples, styling, and coverage remain.

## Removed

### ONNX MiniLM embedding backend

`EMBEDDING_BACKEND=onnx` embedded with Chroma's MiniLM. The example env uses `auto`. A value outside `auto`, `openai`, and `deterministic` now raises, so a leftover `onnx` cannot silently retarget the index. A host that still says `onnx` must switch to `auto` or `openai` and re-ingest.

### Optional demo API key

`DEMO_API_KEY` was empty in the example env files and never entered retrieval or the prompt. Email login, the rate limit, and the daily caps remain.

### Durable chat log file

`data/logs/chat.log` duplicated the `chat_turn` line that stdout already writes. The staff trust panel reads the response, not the file. `l1.log` remains. The service unit does not set `StandardOutput`, so journald keeps the stdout stream. An existing `data/logs/chat.log` is left on disk and is no longer appended.

### HTTP chat options: `k`, `filters`, and `POST /chat/clear`

`POST /chat` accepted a per-request `k` (capped by `MAX_K`) and `filters` (`tipo`, `comm_id`, date range) that dropped citations after the model had answered, which could turn a grounded answer into silencio. `POST /chat/clear` cleared a session. The UI never sent `k` or `filters` and clears with the `/clear` message, so its answers are unchanged; retrieval always uses `DEFAULT_K`. `ChatRequest` still forbids unknown fields, so a client that sends `k` or `filters` now gets HTTP 422 and must drop them. A client that posted `/chat/clear` must post `/chat` with `{"message": "/clear", "session_id": ...}`. A leftover `MAX_K` in an env file is ignored.

### Configurable guardrail policy and shadow mode

`guardrails/policy.yaml`, its hand-written parser `adapters/policy_yaml.py`, and `GUARDRAILS_POLICY_PATH` let an operator reorder, disable, or un-enforce rails; an un-enforced rail logged a block as `pass` with `would_block`. Every rail shipped enabled and enforced, and nothing read the `params` entries, so the order now lives in `domain/guardrails/registry.py` as `RAILS` and every rail always applies. The same rails run in the same order, so the cited clause or silencio is unchanged. The staff trust panel keeps every row, stage, verdict, and detail; it drops the "no aplicado" tag, which never appeared, and the "bloquearía" tag, which only repeated a `block` chip. The `/chat` guardrail rows drop `enforced` and `would_block`, and the `chat_turn` log drops `policy_version`.

### Retrieval and generation tuning settings

`RETRIEVAL_MIN_SCORE` (a cosine floor, 0 = off), `RETRIEVAL_HYBRID=false` (dense-only search), `RETRIEVAL_CANDIDATES`, `INDEX_SPACE`, `LLM_SEED`, `LLM_REASONING_BUDGET`, and `LLM_THINKING_USER_LAYOUT` were all left at their defaults in every env file. Search is now always dense plus BM25 with 20 candidates per side, new collections are always cosine, no seed or reasoning budget is sent, and Usuario turns always run without thinking, which is exactly what the defaults did, so the cited clause or silencio is unchanged. Hits no longer carry the unread `dense_score` and `lexical_rank` metadata. Settings ignore unknown keys, so check the dump host's `.env` for these names: a leftover value is silently dropped. On llama.cpp, raise `LLM_MAX_TOKENS` instead of setting a reasoning budget. An index created with another space keeps it until it is deleted and re-ingested.

### Incremental staff reasoning display

The staff UI's partial reasoning updates, word-boundary throttle, and `OnThinking` callback chain are removed. Operador still shows retrieve/generate/verify progress and the completed provider trace with the final answer. Provider streaming, thinking settings, retries, and timeouts were left in place; Usuario still runs without thinking. That cut left the cited clause or silencio, the `thinking` field, session memory, and the inspector, trust, and L1 panels unchanged.

### Timed send-code status flash

The login card no longer resets send-code success or failure to the idle hint after two seconds. Notices remain until the next auth action or page reload; verification and logout replace the previous notice. Reset timers, timer tokens, DOM readback, and the flash-duration constant are removed. Email code/link login, truthful reuse-or-check-mail copy, allowlist privacy, explicit failures, accessibility, rate limits, and daily caps remain.

### Unshown response and log fields

The retrieval sidecar (top-k ids, fused scores, citation coverage, and the grounded flag), the chat fields `disclaimer` and `abstain_reason`, the health field `embedding_model`, and the log-only measurements (`retrieve_ms`, `llm_ms`, `ttft_ms`, `thinking_chars`, `prompt_tokens`, `completion_tokens`, and per-rail latency) are not drawn by the Usuario or Operador views. They are removed. Citation `tipo` stays on the citation and in the model JSON. A turn that searched is still remembered for follow-ups, including an empty search; an input block, an index that is not ready, `/clear`, and a failed language-model call stay unremembered. The shown answer, Fuente line, freeze sentence, silencio banner, phase line, footer, examples, login, Operador thinking trace, citation card, trust chips, and Calidad L1 stay. `Settings.embedding_model` still selects the embedding model. The interface footer still states that the extract is unofficial. Provider streaming, the stream loop, thinking assembly, and the truncation check stay. L1 sample latency stays.
