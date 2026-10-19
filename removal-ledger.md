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

## Removed

### ONNX MiniLM embedding backend

`EMBEDDING_BACKEND=onnx` embedded with Chroma's MiniLM. The example env uses `auto`. A value outside `auto`, `openai`, and `deterministic` now raises, so a leftover `onnx` cannot silently retarget the index. A host that still says `onnx` must switch to `auto` or `openai` and re-ingest.

### Optional demo API key

`DEMO_API_KEY` was empty in the example env files and never entered retrieval or the prompt. Email login, the rate limit, and the daily caps remain.

### Durable chat log file

`data/logs/chat.log` duplicated the `chat_turn` line that stdout already writes. The staff trust panel reads the response, not the file. `l1.log` remains. The service unit does not set `StandardOutput`, so journald keeps the stdout stream. An existing `data/logs/chat.log` is left on disk and is no longer appended.
