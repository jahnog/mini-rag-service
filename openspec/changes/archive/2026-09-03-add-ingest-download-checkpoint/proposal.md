## Why

Cited CAMEX clauses with visible guardrails and L1 numbers need a dump that survives a crash during embeddings: today a GET is forgotten until the serving-index write finishes, so an interrupted texto ordenado upsert re-downloads from BCRA and never starts the Comunicaciones A. Operators also cannot see that a new PDF is being fetched, and the host embedding server’s 1024-token context cannot ingest unbounded chunks.

## What Changes

Nothing is **BREAKING**.

- One-time ingest and refresh persist a **dump checkpoint** (raw PDF + extract + sha256) when a new document is stored on disk, **before** the serving-index upsert. Index completeness is a separate `indexed` flag on that same manifest row.
- A later run **MUST NOT** re-download an id whose dump checksum still matches; if the dump exists and the index write did not finish, ingest rebuilds the index from the stored extract.
- Dump-only rows do **not** complete one-time ingest (`last_refresh` stays unset until the full run finishes).
- Operators see **download started**, **dump checkpointed**, and **index complete** in the same console and ingest log file, only for documents actually fetched or indexed (skips stay on the existing started/finished events).
- Each indexed chunk **MUST** fit the configured embedding input limit so the host embedding server can embed it. Strategy B still splits on puntos; oversized units are subdivided and keep the punto id.

## Capabilities

### New Capabilities

- None.

### Modified Capabilities

- `corpus-ingest`: dump checkpoint after extract is stored; skip re-download when sha256 matches; repair index from extract when dumped but not indexed; dump-only is not a completed one-time ingest.
- `ingest-logging`: log download started, dump checkpoint, and index complete for documents actually fetched or indexed.
- `retrieval`: each indexed chunk MUST fit the configured embedding input limit; oversized strategy-B units keep the punto id on each part.

## Non-goals

- Banxico or any non-`bcra.gob.ar` corpus.
- Next.js v1.
- LlamaIndex.
- Redis.
- Filling the 1990–97 CAMEX catalog hole.
- GitHub-hosted vector index.
- Catalog pagination changes, empty-catalog `mark_complete`, concurrent document downloads.
- A tokenizer / exact token counts, lowering `EMBEDDING_BATCH_SIZE`, or raising host `n_ctx`.
- Log rotation, a new CLI flag, or health-schema changes.

## Impact

- `IngestCorpus` writes a dump checkpoint then an indexed checkpoint; resume uses dump files (including orphan raw+extract with no row).
- Manifest document entries gain `indexed` (absent means already indexed, for dumps written under the old atomic-after-upsert rule).
- Chunkers A/B and the embedding clip share `EMBEDDING_MAX_CHARS` (default 2048 for the host 1024-token server). Existing `data/index` must be wiped once; dump PDFs can stay.
- Unit tests cover dump-before-index resume, download logs, orphan files, legacy `indexed`, and chunk size caps. `src` coverage stays >= 80%.
- No new Python dependencies. No change to the five ports, composition graph, chat API, or Gradio UI.
