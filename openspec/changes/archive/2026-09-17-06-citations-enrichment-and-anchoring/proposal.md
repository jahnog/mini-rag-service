## Why

Cited CAMEX clauses with visible guardrails and L1 numbers. The citation card in the observatory shows `texto_ordenado · fecha — · punto 8.4.1` with no link because `fecha` and `url` only reach a citation if the model happens to emit them (`_citation` in `src/bcra_rag/adapters/llm_openai.py:140-147`); the manifest and chunk metadata already hold both (`data/bcra/current/MANIFEST.json` documents carry `url`, `fecha`, `title`). Cite-or-abstain is all-or-nothing on a normalized substring (`domain/guardrails/output.py:220-241`): one paraphrased word turns a correct answer into silencio, which is why `citation_snippet_grounded` is 0.27 in `evals/l1.json`. A named Comunicación fetch joins its chunks in Chroma's unordered `get` result and slices the first 2000 characters (`adapters/index_chroma.py:149-160`), then the prompt clips each chunk at 1500 (`use_cases/answer_query.py:670`), so long Comunicaciones lose most of their text and a requested punto silently falls back to the whole document.

## What Changes

- After the model's citations are validated, the system SHALL fill `fecha`, `url` and (when the model omitted it) `punto` from the dump manifest and the matching chunk; the model is no longer asked for `fecha`/`url`.
- Cite-or-abstain SHALL anchor a snippet that is not an exact normalized substring to the longest verbatim run of that snippet in the cited document when that run is at least 40 characters or at least 60% of the snippet; the snippet is replaced by that verbatim run and the verdict is `warn` "cita ajustada". Snippets with no such run still fail. (MODIFIED `guardrails` "Cite or abstain".)
- Sections fetched for a named Comunicación SHALL be assembled in document order (an `ordinal` written at ingest, with a punto-number fallback for existing indexes), SHALL prefer the requested punto with its sub-puntos plus one neighbour on each side, and SHALL be capped by a new `CONTEXT_CHUNK_CHARS` setting (default 3000) that also replaces the fixed 1500-character clip in the prompt.

## Capabilities

### New Capabilities

- (none)

### Modified Capabilities

- `query-answering`: citation enrichment from the dump; context chunk cap.
- `guardrails`: anchored citations.
- `retrieval`: ordered named sections.

## Non-goals

- Banxico or any non-`bcra.gob.ar` corpus.
- Next.js v1.
- LlamaIndex.
- Redis.
- Filling the 1990–97 CAMEX catalog hole.
- GitHub-hosted vector index.
- Re-ingesting the corpus in this change (the ordinal fallback keeps existing indexes working; a re-ingest adds `ordinal`).
- Hybrid retrieval and the similarity floor (change 08).

## Impact

- `src/bcra_rag/use_cases/answer_query.py` (`enrich_citations`, `generate_from_context(doc_meta=…)`, `_prompt` cap), `src/bcra_rag/domain/guardrails/output.py` (`anchor_span`, `CiteOrAbstainRail`, `_quote_ok`), new `src/bcra_rag/domain/sections.py`, `src/bcra_rag/adapters/index_chroma.py` and `index_fake.py` (`get_section`), `src/bcra_rag/domain/router.py` (`_chunk_from_section` metadata), `src/bcra_rag/use_cases/ingest_corpus.py` / `domain/chunkers.py` (ordinal), `src/bcra_rag/settings.py` (`context_chunk_chars`), `src/bcra_rag/adapters/llm_openai.py` (system prompt citation object drops fecha/url — text only).
- Callers kept working: `src/bcra_rag/evals/use_cases/run_generation.py` (new `doc_meta` keyword optional).
- Tests: `tests/test_answer_query.py`, `tests/test_guardrails.py`, `tests/fixtures/guardrail_probes.jsonl`, `tests/test_index.py`, `tests/test_ingest.py`, new `tests/test_sections.py`, `tests/test_ui.py` citation card.
- README Ingest/Debug mention `CONTEXT_CHUNK_CHARS` and the ordinal re-ingest note. No command change.
