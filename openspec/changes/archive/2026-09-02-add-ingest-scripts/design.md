## Context

Empty runtime. This change owns `corpus-ingest`; sibling `bcra-mini-rag` is rebased so it no longer ADDs that capability. See `proposal.md` Why. Behavior: `specs/corpus-ingest/spec.md`.

Constraints that shape this slice: Python 3.11+ via uv; pydantic v2; thin hexagon; living dump `data/bcra/current/` + `data/index/` on the deploy host; BCRA CAMEX A + `t-excbio.pdf` only; OpenAI-compatible embeddings; no GitHub-hosted index.

Probed 2026-09-02 (same facts as the sibling design): buscador `POST /api/endpoints/buscador-comunicaciones.php` `mode=tipo-circular&tipo=A&circular=CAMEX` → 992/974 unique PDFs; TO at `https://www.bcra.gob.ar/Pdfs/Texord/t-excbio.pdf` (last incorporated A 8307, 25/08/2025). Catalog through A 8464 (2026-08-06). CAMEX seq hole 232→314 (1990–97).

## Goals / Non-Goals

**Goals:**

- Two operator modules: `jobs.ingest` (one-time, resumable until `last_refresh` is set) and `jobs.refresh` (append + TO checksum replace).
- Shared `IngestCorpus` use case: catalog → polite fetch → classify → extract → index upsert → MANIFEST checkpoint.
- Ports needed for that path (`CatalogPort`, `ExtractorPort`, `IndexPort`) plus a composition root and Settings.
- Host-side refresh (compose or crontab) on the volume that holds the dump; compose jobs are one-shot and not in default `up`.

**Non-Goals (design-level):**

- `AnswerQuery`, `RunL1`, Gradio, FastAPI chat, session memory, query router, guardrails.
- Wiring `LlmPort` / `SessionStore` beyond Protocol stubs so the five-port hexagon stays intact.
- DI container, Redis, CQRS, LlamaIndex, second FAISS index, GHA-hosted Chroma, filling 1990–97.

## Decisions

### Decision: Five ports, implement three

Keep the sibling hexagon: `CatalogPort`, `ExtractorPort`, `IndexPort` (owns embeddings: upsert + search + get_section), `LlmPort`, `SessionStore`. This change implements the first three and the `IngestCorpus` use case. `src/bcra_rag/composition.py` wires `Settings`. `LlmPort` and `SessionStore` remain empty Protocol stubs (no adapters) so chat can land later without a second architecture.

Alternatives: a standalone ingest script with no ports (fights the hexagon); an EmbeddingsPort (YAGNI — Index owns embeddings).

### Decision: Two CLIs, one use case

| Operator job | Module | Mode |
|---|---|---|
| One-time ingest | `python -m bcra_rag.jobs.ingest` | `full`: empty dump loads catalog + TO + index; interrupted dump **resumes**; after `last_refresh` is set, unknown catalog ids are **not** fetched |
| Refresh | `python -m bcra_rag.jobs.refresh` | `refresh`: refuse unless a successful checkpoint exists **and** `last_refresh` is set; else append unknown ids and rebuild TO only on checksum change |

Shared pipeline inside `IngestCorpus`. Checkpoint MANIFEST per document **after** extract and index upsert succeed. Do not write a success MANIFEST before the first stored document (missing file, empty `{}`, or placeholder are not a completed dump). First successful full run and each successful refresh set `last_refresh`. `last_comm_id` is the highest stored Comunicación A id.

Refresh exits non-zero with an operator message (do not start a catalog crawl) when MANIFEST is missing, empty, or `last_refresh` is unset.

Console-script aliases MAY be added in `pyproject.toml`; the modules above are the contract.

Alternatives: one CLI with subcommands (less obvious for crontab); refresh bootstraps an empty dump (hides the one-time vs refresh split).

### Decision: Dump layout and classifier

Dump: `data/bcra/current/{MANIFEST.json,NOTES.md,raw/,extract/}` and `data/index/`. MANIFEST keyed by comunicación id (duplicate catalog rows collapse). `NOTES.md` mentions the 1990–97 CAMEX tag hole (plus README). Catalog newest-first.

Classification (same as sibling):

- TO reprint pack → short event (wins if the title is also Adecuación).
- Other CAMEX A, including Adecuaciones → full extract.
- TO `t-excbio.pdf` → full structure-aware extract + `to_as_of` from the header.
- Post-TO A’s (`fecha_emision > to_as_of`) stay full text.

Do not write `aliases.json` in this change (retrieval concern).

### Decision: Polite BCRA I/O

Buscador: `https://www.bcra.gob.ar/api/endpoints/buscador-comunicaciones.php`. PDFs: `/archivos/Pdfs/comytexord/A{nnnn}.pdf` (zero-padded early ids). TO: `https://www.bcra.gob.ar/Pdfs/Texord/t-excbio.pdf`.

`httpx` + semaphore 2–4, ~200ms gap, identifiable User-Agent. BCRA `HEAD` can lie: GET the first bytes / content-type before storing a PDF. Reject non-`bcra.gob.ar` hosts before any request. Extract UTF-8 with latin-1/cp1252 fallback via `pdftotext` (poppler) on CPU (`asyncio.to_thread`). Hyphen-join and strip running headers (`B.C.R.A. EXTERIOR Y CAMBIOS Sección N`).

CI never hits the live buscador: catalog and PDF tests use respx (or equivalent) fixtures.

### Decision: Chroma on disk, upsert on change

IBM 3 take for this slice. One serving collection under `data/index/`. `IndexPort.upsert` after each stored extract and **before** the MANIFEST checkpoint. Skip upsert only when MANIFEST sha256 is unchanged **and** the index already contains that id; if the dump has the id and the index does not, re-upsert from the stored extract.

When the TO checksum changes: delete existing TO chunks for that `doc_id`, then upsert the new extract so dropped or renumbered puntos do not linger.

Chunking so the index is not empty for later chat (implementation names live here, not in specs):

- A: ~512 / 128 after hyphen-join and header strip.
- B: `Sección N`, `^\d+(\.\d+)*\.?`, Anexo; merge children under ~80 tokens; prepend `heading_path`.
- Serving: B on TO + clean A’s, A on the rest; store `chunker` on metadata. Event records are upserted too.
- Stable ids `{doc_id}:{punto|digest}`. Metadata: `doc_kind`, `fecha`, `numero`, `punto`, `chunker`, `doc_part`.

L1 A/B rebuild, query router, and `get_section` callers are **not** this change; Index may expose `search`/`get_section` as no-op-safe methods so the port stays complete. Sibling retrieval implements those callers.

FAISS only if Chroma slips. No second live collection.

### Decision: Package skeleton, no API process

`uv` package `bcra_rag` under `src/bcra_rag`. Settings via pydantic-settings: `DATA_DIR`, `EMBEDDING_*`, concurrency/delay, User-Agent. `.env.example` lists those keys. structlog JSON.

Dockerfile + compose **job** services (poppler, volume for dump and index). Services are one-shot (`restart: "no"`) and sit behind a compose profile (or equivalent) so default `docker compose up` does **not** start ingest or refresh. No Gradio/FastAPI process in this change.

README states: install poppler for non-Docker `python -m` runs; `EMBEDDING_*` is required for a real index upsert (CI uses a fake IndexPort); run `jobs.ingest` once on the volume host; schedule `jobs.refresh` there (crontab or compose profile); a second ingest after `last_refresh` does not pull new catalog ids; wipe and rebuild by deleting the volume; GitHub Actions cannot persist Chroma.

### Decision: IBM 1–4 take/leave (ingest slice)

| Take | Leave |
|---|---|
| Chroma on disk; upsert on refresh | LlamaIndex; GHA-hosted Chroma |
| Index owns embeddings | Extra EmbeddingsPort; FAISS second index |
| Structured dump + MANIFEST resume | Dated dump folders (fight cron) |
| Host crontab/compose profile for refresh | Recommender; chat loop |

### Decision: Slip order (this slice)

Never cut: TO + post-TO ingest, resume + refresh CLI, `last_refresh`, polite download, unit tests with fakes, uv/ruff/mypy/pytest.

Product slips that stay out of this change: deontic scan (slip-first in the sibling design only), streaming, Gradio, L1.

## Risks / Trade-offs

- [BCRA IP block] → politeness + resume from MANIFEST.
- [HEAD lies / HTML error page stored as PDF] → GET first bytes and content-type; do not store non-PDF.
- [1990–97 hole] → document in NOTES.md; do not crawl untagged A ids.
- [TO stale vs catalog] → still ingest post-`to_as_of` A’s in full; vigente routing is later.
- [Truncating all A’s] → only reprint packs become events.
- [GHA cannot hold index] → jobs run on the volume host only.
- [Empty volume + refresh] → refuse with operator message; one-time ingest is the bootstrap.
- [Interrupted first run + refresh] → refuse until `last_refresh` is set.
- [Dump checkpointed, index missing] → re-upsert from extract; do not skip solely on MANIFEST sha256.
- [Stale TO puntos after replace] → delete TO chunks for that `doc_id` then upsert.
- [Default compose up races refresh] → one-shot profile; refresh not in the default project.
- [Public embedding bill] → upsert only changed ids; CI uses a fake IndexPort.
- [Hexagon bloat] → three live ports; two stubs; no chat graph.

## Migration Plan

Greenfield. Deploy: Docker Compose job image (poppler, named volume). Operator runs `python -m bcra_rag.jobs.ingest` once, then schedules `python -m bcra_rag.jobs.refresh` on that host (crontab or compose profile, not default `up`). Rollback: delete the volume; no user data. Apply this change before `bcra-mini-rag`. Sibling tasks extend the package and add API+Gradio; they do not re-implement ingest.

## Open Questions

None that change specs. Embedding provider and model names are Settings values. Exact semaphore size in 2–4 and the ~200ms gap are configuration, not behavior.
