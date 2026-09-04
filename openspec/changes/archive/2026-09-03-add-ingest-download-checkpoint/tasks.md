## 1. corpus-ingest

- [x] 1.1 Add `Manifest.is_indexed` (missing key ⇒ true) and merge on `checkpoint` so a second write cannot drop sha/url/title/fecha. Verify a unit assertion: a row without `indexed` is indexed; merging `{indexed: true}` keeps `sha256`
- [x] 1.2 In `IngestCorpus`, dump-checkpoint after raw+extract, then `delete_document` + upsert from extract, then `indexed: true`. Shared helper for TO and Comunicación. Verify `uv run pytest tests/test_ingest.py tests/test_refresh.py -q`: A8464 upsert boom leaves A8464 in MANIFEST with `indexed` false; resume does not GET A8464; TO upsert boom does not GET `t-excbio.pdf` again; orphan raw+extract with no row is not re-downloaded; legacy row without `indexed` is not re-upserted; refresh still refuses while `last_refresh` is unset

## 2. ingest-logging

- [x] 2.1 Log `ingest_document_download_started` (doc_id, name, fecha, url) before GET, `ingest_document_downloaded` (doc_id, sha256) after dump checkpoint, `ingest_document_indexed` (doc_id) after upsert. Skips must not emit those events. Verify `uv run pytest tests/test_ingest.py -q`: a new A13 run includes the three events and url; a second matching-sha run does not

## 3. retrieval

- [x] 3.1 Default `EMBEDDING_MAX_CHARS=2048` in Settings, `.env.example`, and `deploy/env.remote.example`. Embeddings clip at that default. Verify `uv run pytest tests/test_settings.py tests/test_embeddings.py tests/test_deploy.py -q`: default is 2048; a 3000-char embed is clipped; remote env has `EMBEDDING_MAX_CHARS=2048`
- [x] 3.2 Chunker A default 256/64; both chunkers take `max_chars`; B splits heading+body so each chunk `len(text) <= max_chars` and keeps `punto`. Wire `IngestCorpus` and `rebuild_structured_slice`. Verify `uv run pytest tests/test_chunkers.py tests/test_router.py -q`: default A on 600 words yields more than two chunks; explicit 512/128 overlap test still passes; oversized B unit splits with the same punto; a 256-long-word A window still caps at max_chars
- [x] 3.3 If README `## How to run` mentions embedding batch size, note the 2048-char cap for the 1024-token host server. Verify `uv run pytest tests/test_notes.py::test_readme_operator_bullets -q` after any README edit
- [x] 3.4 Run `uv run pytest -q` and `uv run pytest -q --cov=src --cov-report=term-missing --cov-report=xml` and fix until green with src coverage >= 80%
