## Why

Cited CAMEX clauses with visible guardrails and L1 numbers. Retrieval is dense-only: `ChromaIndex.search` (`src/bcra_rag/adapters/index_chroma.py:87-147`) runs one embedding query in the collection's default L2 space, scores `1/(1+distance)` and never thresholds, so exact tokens that matter in this corpus ("A 3500", "punto 8.4.1", "MULC", "SECOEXPO") get no lexical credit and there is no data-driven silencio when nothing is close — L1 shows hit@5 0.87 but `citation_id_exact` 0.23 and slices `vigente 0.0`, `obligacion 0.0` (`evals/l1.json`). Every turn also blocks the event loop: `dump_health` (`domain/health.py`) re-reads `MANIFEST.json` and asks Chroma `has_document` synchronously, `Manifest.load` runs a second time (`use_cases/answer_query.py:255`), and `Router.route` → `ChromaIndex.search` (embedding HTTP + HNSW) executes inline in the async `_respond` (`:138,:259`), so concurrent observatory users stall each other for the 200–500 ms retrieval window.

## What Changes

- `ChromaIndex.search` SHALL combine dense results with an in-package BM25 lexical index over the collection's chunks using reciprocal-rank fusion (`RETRIEVAL_HYBRID`, default true; `RETRIEVAL_CANDIDATES`, default 20), keeping the `IndexPort` contract and score field semantics.
- New collections SHALL be created with cosine space (`INDEX_SPACE`, default `cosine`); existing collections keep their space until re-ingested.
- A similarity floor (`RETRIEVAL_MIN_SCORE`, default 0 = off) SHALL empty the result set when the best dense cosine similarity is below it, so the router returns silencio `empty_hits`; the floor applies only to cosine collections.
- The manifest and health document SHALL be cached by file identity (path, mtime, size), and retrieval and health SHALL run off the event loop via `asyncio.to_thread`.

## Capabilities

### New Capabilities

- (none)

### Modified Capabilities

- `retrieval`: hybrid lexical+dense search; cosine space for new collections; similarity floor.
- `platform`: retrieval and health off the event loop; cached manifest.

## Non-goals

- Banxico or any non-`bcra.gob.ar` corpus.
- Next.js v1.
- LlamaIndex.
- Redis.
- Filling the 1990–97 CAMEX catalog hole.
- GitHub-hosted vector index.
- A cross-encoder reranker (needs torch/sentence-transformers or a llama.cpp `/rerank` endpoint).
- A new dependency for BM25 (`rank-bm25` is not added; ~60 lines in the domain).
- Migrating an existing L2 collection in place (operator wipes `data/index` and re-ingests to switch space).

## Impact

- New `src/bcra_rag/domain/bm25.py`, `src/bcra_rag/domain/text.py` (Spanish stoplist moved from `adapters/index_fake.py`), `src/bcra_rag/adapters/index_chroma.py` (lexicon cache, fusion, floor, space), `src/bcra_rag/settings.py` (four settings), `src/bcra_rag/domain/manifest.py` (`load_cached`), `src/bcra_rag/domain/health.py` (cache), `src/bcra_rag/use_cases/answer_query.py` (`asyncio.to_thread`).
- Tests: new `tests/test_bm25.py`, `tests/test_index.py`, `tests/test_health.py`, `tests/test_answer_query.py`, `tests/test_settings.py`.
- README Ingest/Debug: the four settings and the re-ingest note. Rerun L1 afterwards (operator).
