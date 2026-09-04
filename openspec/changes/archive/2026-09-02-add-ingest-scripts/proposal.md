## Why

Cited CAMEX clauses with visible guardrails and L1 numbers need a living dump and index on the host before chat exists. The repo has no operator path to load the official CAMEX A catalog plus the Exterior y Cambios texto ordenado once, then refresh that dump when new comunicaciones appear.

## What Changes

Nothing is **BREAKING** (greenfield runtime). This change owns `corpus-ingest`. Sibling `bcra-mini-rag` is rebased in the same pass so it no longer ADDs that capability.

- Add a **one-time ingest** operation: empty dump → official CAMEX tipo-A catalog (A 13 / 1981 → present) plus current texto ordenado, extracts, atomic MANIFEST checkpoints, and serving index.
- Add a **refresh** operation on the same dump (the original request called this “update”): append CAMEX A ids not yet in the manifest; replace the texto ordenado only when its checksum changed; upsert the index; set `last_refresh`. After a completed one-time ingest, re-running one-time ingest does not pull new catalog ids.
- Both operations stay on `bcra.gob.ar` and stay polite toward the BCRA host. Interrupted one-time ingest resumes remaining work; refresh refuses until one-time has completed.
- Document the 1990–97 CAMEX tag hole in an operator dump note; do not crawl untagged A ids to fill it.
- Schedule refresh on the machine that holds the dump (compose or crontab), not on a GitHub-hosted runner.

Assumption recorded: “injection scripts” in the request means corpus ingest/index load (one-time + refresh), not prompt-injection tests. Prompt-injection remains a guardrail in `bcra-mini-rag`.

## Capabilities

### New Capabilities

- `corpus-ingest`: Official CAMEX A + texto ordenado dump, classification, resumable one-time ingest, host-side refresh, unique ids, dump note for the catalog hole, serving-index upsert on the same host.

### Modified Capabilities

- None (main `openspec/specs/` is empty). Sibling `bcra-mini-rag` no longer drafts `corpus-ingest`.

## Non-goals

- Banxico or any non-`bcra.gob.ar` corpus.
- Next.js v1.
- LlamaIndex.
- Redis.
- Filling the 1990–97 CAMEX catalog hole.
- GitHub-hosted vector index (or GitHub Actions as the place the index lives).
- Chat API, Gradio UI, L1 evals, query guardrails, session memory.
- PSP/SINAP/QR corpus, login, design system, HITL/multi-agent.

## Impact

- New Python package skeleton `src/bcra_rag` (uv, Settings, ports needed for ingest: Catalog, Extractor, Index), composition root, dump under `data/bcra/current/` and index under `data/index/`.
- Operator modules `python -m bcra_rag.jobs.ingest` and `python -m bcra_rag.jobs.refresh`; Docker volume; compose job services are one-shot and not started by default `compose up`.
- External: BCRA buscador and `bcra.gob.ar` PDFs only; OpenAI-compatible embeddings for index upsert.
- Tests: pytest unit tests with HTTP fakes (respx); no paid L1; no live BCRA crawl in CI.
- Chat, UI, and evals stay in `bcra-mini-rag` and are not implemented here. Apply this change before `bcra-mini-rag`.
