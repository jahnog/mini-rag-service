## Context

See proposal.md Why and `specs/corpus-ingest/spec.md`, `specs/ingest-logging/spec.md`, `specs/retrieval/spec.md`.

Product runtime already exists. Unchanged architecture (restated so this design satisfies the constitution):

- **Ports:** Catalog, Extractor, Index (owns embeddings), Llm, SessionStore. This change does not add a port.
- **Composition:** `build_ingest` / `build_app`; no DI container.
- **Ingest/refresh pipeline:** catalog → polite fetch → classify → extract → chunk A/B → index upsert → MANIFEST. Today the MANIFEST row is written only after upsert. `jobs.ingest` runs `IngestCorpus.run("full")`; `jobs.refresh` runs `run("refresh")` and refuses until `last_refresh` is set.
- **Router / chunking / session:** aliases; named Com. A `get_section` vs vigente (TO ∪ later A’s); serving uses structured chunker B on TO + clean A’s and fixed A otherwise; in-process session, one worker, `/clear`.
- **Host-side refresh:** systemd oneshots + cron.d on the dump host.

Constraints: Python 3.11+ via uv; structlog JSON to stdout and `DATA_DIR/logs/ingest.log` for jobs. Host embeddings: a configured OpenAI-compatible `qwen3-embedding-0.6b` endpoint with **n_ctx = 1024**. `EMBEDDING_MAX_CHARS` is currently 8000; chunker A is 512/128 words; chunker B has no max.

## Goals / Non-Goals

**Goals:**

- Split dump vs index checkpoints on each MANIFEST document row (`indexed`).
- Resume skips BCRA GET when dump sha256 matches local files (including orphan raw+extract).
- When `indexed` is false, delete then upsert from extract (Chroma partial batches).
- Log `ingest_document_download_started` / `downloaded` / `indexed` only on the real fetch/index path.
- Size chunks and clip embeddings to `EMBEDDING_MAX_CHARS=2048` so each item fits 1024-token context.

**Non-Goals (design-level):**

- Changing ports, catalog filters, health schema, or `EMBEDDING_BATCH_SIZE`.
- A tokenizer. Char/word budget is the contract.
- Mid-batch embedding resume. Full re-upsert from extract only.
- Raising the embedding host `n_ctx`.

## Decisions

### Decision: `indexed` on the same MANIFEST row

Dump checkpoint writes sha256, kind, url, title/fecha, `indexed: false` after raw+extract are on disk. After `IndexPort.upsert` returns, merge `indexed: true` (do not drop fields). `Manifest.is_indexed(doc_id)`: missing key ⇒ `true` (legacy rows were only written after upsert).

`last_refresh` still only at `mark_complete()`. Refresh still refuses while it is unset. `has_document` is not completeness.

Alternatives: a second MANIFEST file (split brain); treating `has_document` as done (false complete after a partial Chroma batch).

### Decision: Shared dump-then-index helper in `IngestCorpus`

TO and Comunicación skip logic already diverges (`replace`, `last_refresh`, classify). One helper owns: skip / orphan / download / dump checkpoint / delete+upsert / indexed checkpoint / the three new log events. `_ingest_to` keeps replace/`to_as_of`; `_ingest_comunicacion` keeps classify and event truncation.

Logs (existing dual sink): `ingest_document_download_started` (`doc_id`, `name`, `fecha`, `url`); `ingest_document_downloaded` (`doc_id`, `sha256`); `ingest_document_indexed` (`doc_id`). Emit from the use case, not ChromaIndex or the fetcher.

Orphan path: if raw PDF + extract exist and there is no row (or sha missing), hash the local PDF, write dump checkpoint, index from extract, no GET.

When `indexed` is false: always `delete_document` then upsert from extract.

Alternatives: duplicate the sequence in both ingest methods (will drift).

### Decision: 2048-char ceiling, no tokenizer

Host n_ctx=1024. Spanish legal text ~2 chars/token plus BOS/EOS → default `EMBEDDING_MAX_CHARS=2048`. Settings, `.env.example`, `deploy/env.remote.example`. Embeddings still clip at that cap; retry-halving stays for unexpected overflow.

Chunker A default **256 / 64** words (was 512 / 128). Chunker B keeps punto/section splits and the 80-word child merge, then splits any unit whose **final text** (heading_path + body) exceeds `max_chars`. Heading counts toward the cap. Unique ids via body digest; `punto` copied onto each part.

Both chunkers take `max_chars`. `IngestCorpus` and `rebuild_structured_slice` pass `settings.embedding_max_chars` so L1 A/B matches serving.

Keep `EMBEDDING_BATCH_SIZE=8` (per-item context). After deploy, wipe `data/index` once; dump PDFs stay.

Alternatives: tiktoken (new dep, YAGNI); lower batch size (wrong failure mode); raise n_ctx (host change, out of scope).

### Decision: IBM 1–4 take/leave (unchanged)

| Take | Leave |
|---|---|
| Chroma on disk; upsert on refresh | LlamaIndex; GHA-hosted Chroma |
| Index owns embeddings | Extra EmbeddingsPort; FAISS second index |
| Structured dump + MANIFEST resume | Dated dump folders |
| Host crontab/compose/systemd for refresh | Recommender; GitHub-hosted vector index |

### Decision: Slip order

Never cut: dump checkpoint before index; skip re-GET; download/index logs; 2048-char chunk cap; unit tests; src coverage >= 80%.

Deontic scan stays slip-first in design only.

## Risks / Trade-offs

- [Partial Chroma + `has_document` true] → `indexed` false forces delete+upsert from extract.
- [Legacy dumps without `indexed`] → missing key means true.
- [256-word A window still >2048 chars] → split so every `chunk.text` is `<= max_chars`.
- [2048 is tight at 2 chars/token] → clip + retry-halving; no tokenizer.
- [Health `n_docs` counts dump-only rows] → accepted; `last_refresh` is the complete signal.
- [Chunk ids change for oversized units] → wipe `data/index` once.
- [API serving mid-ingest] → deploy already stops the API during the job.

## Migration Plan

No dump-format migration beyond additive `indexed`. Next `jobs.ingest` writes dump checkpoints as it goes. Operators wipe `data/index` once, then re-run one-time ingest (orphan TO extract is not re-downloaded). Rollback: revert the change; leftover `indexed` keys are ignored by old code. Host deploy is existing `./scripts/deploy.sh`.

## Open Questions

None.
