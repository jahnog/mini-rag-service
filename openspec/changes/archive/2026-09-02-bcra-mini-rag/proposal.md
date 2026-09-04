## Why

Path C needs a public RAG showcase that is not another generic chatbot. A payments/FX/compliance person should ask what a BCRA CAMEX circular says and get a **cited clause** (Comunicación “A” number + punto) or honest **silencio**, with **guardrails visible on that query** and **L1 numbers** (citation-id exact, hit@k, chunking A/B) on the same screen.

## What Changes

Nothing is **BREAKING**. Apply **on top of** landed `add-ingest-scripts` (already archived), which owns the living dump and host-side refresh. This change does not re-specify ingest.

- Use the CAMEX A + texto ordenado dump and `jobs.ingest` / `jobs.refresh` from `add-ingest-scripts` on the same host volume.
- Answer questions with a structured response: short paragraph, `Fuente:`, citations, finding, abstain, per-query guardrail log, cheap retrieval sidecar.
- Route named `Com. A NNNN` to an exact fetch; prefer TO + post-TO A’s for “vigente”; one cross-ref hop; silencio only when the asked-for rule lives in a missing target.
- Session memory (last 6 messages) and `/clear`.
- Gradio UI on FastAPI: freeze/last_refresh banner, chat, citation inspector, L1 accordion. No Next.js in this change.
- Offline L1 evals written to static JSON; never computed in the browser; not on every refresh. Shipped L1 numbers are labeled unpublished until an operator run.
- `/health` HTTP 200 with `index_ready=false` when the index is empty (not 503); crude rate limit; disclaimer on every answer.

Non-goals: Banxico or any non-`bcra.gob.ar` corpus; Next.js v1; LlamaIndex; Redis; filling the 1990–97 CAMEX tag hole; GitHub-hosted vector index; PSP/SINAP/QR; login/design system; HITL/multi-agent (Project 2); L1 on every cron tick; deontic-scan as a v1 MUST; a second catalog/ingest pipeline; LangGraph as a required runtime.

## Capabilities

### New Capabilities

- `retrieval`: Chunking A/B, named-document fetch, vigente routing, aliases, one-hop xref or silencio.
- `query-answering`: Structured cited answers, session memory, `/clear`, HTTP chat API.
- `guardrails`: Per-query pass/warn/block (cite-or-abstain, freeze honesty, scope, injection, no-advice). Deontic scan is not a v1 MUST.
- `evals-l1`: Gold set, citation-id exact and related L1 metrics, static `l1.json`.
- `assistant-ui`: Gradio chat + inspector + L1 accordion + Clear + canned prompts.
- `platform`: Health, rate limit, disclaimer, tests/coverage, Docker volume for dump and index.

### Modified Capabilities

- None (main `openspec/specs/` is still empty; ingest was archived without a spec sync). `corpus-ingest` is not modified here.

## Impact

- Extend the `src/bcra_rag` package from `add-ingest-scripts` with FastAPI + Gradio, a deterministic chat graph, and health. Same Docker volume; API compose service (one worker) on top of existing one-shot ingest/refresh jobs.
- External: BCRA dump already on the host; OpenAI-compatible LLM and embeddings.
- Tests: pytest unit + Gherkin acceptance; L1 is a separate on-demand command.
- After archive, the six capabilities in this change join main specs (plus `corpus-ingest` from `add-ingest-scripts`).
