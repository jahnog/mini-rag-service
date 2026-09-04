## Why

Cited CAMEX clauses with visible guardrails and L1 numbers. The dump is already searchable, but chat still answers “No hay modelo disponible…” because the language model returns `citations` as a string (for example `Fuente: texto_ordenado`) and that payload is treated as a failed model call, so dump hits never reach the user.

## What Changes

Nothing is **BREAKING**.

- Coerce messy language-model JSON (`citations` as a string, a list of strings, or objects missing `tipo`) into a structured draft.
- When that coercion yields no citation objects, dump hits still populate the public citations.
- `llm_unavailable` remains the abstain reason only when the language-model **call** fails (missing key, HTTP, timeout), not when citation JSON is messy.
- The generation prompt states that `citations` is an array of objects and that `Fuente:` belongs in `answer`.
- HTTP `POST /chat` citations stay objects with dump document `id` and `tipo`. Unparseable non-JSON bodies MAY still abstain as a failed call.

## Capabilities

### New Capabilities

- None.

### Modified Capabilities

- `query-answering`: in-corpus answers MUST still cite dump documents when the model’s `citations` field is messy; `llm_unavailable` is reserved for a failed language-model call.

## Non-goals

- Banxico or any non-`bcra.gob.ar` corpus.
- Next.js v1.
- LlamaIndex.
- Redis.
- Filling the 1990–97 CAMEX catalog hole.
- GitHub-hosted vector index.
- Re-ingest, wiping `data/index`, or repairing Chroma HNSW queue lag.
- Renaming the default `LLM_MODEL`.
- Gradio layout or a new UI.
- A new port, DI container, or `response_format=json_schema`.

## Impact

- Language-model adapter parses and coerces the completions JSON before the draft is validated.
- Query-answering prompt text is tightened; retrieval, merge-from-hits, guardrails, and HTTP `ChatResponse` shape stay.
- Unit tests cover messy `citations` shapes and keep the existing failed-call silencio. `src` coverage stays >= 80%.
- No new Python dependencies. No change to Catalog, Extractor, Index, or SessionStore ports, composition, ingest/refresh, or Gradio mount.
