## Context

See proposal.md Why and `specs/ingest-logging/spec.md` for the operator contract.

Product runtime already exists. Unchanged architecture (restated so this design satisfies the constitution):

- **Ports:** Catalog, Extractor, Index (owns embeddings), Llm, SessionStore. This change does not add a port.
- **Composition:** `build_ingest` / `build_app`; no DI container.
- **Ingest/refresh pipeline:** catalog → polite fetch → classify → extract → chunk A/B → index upsert → MANIFEST checkpoint. `jobs.ingest` runs `IngestCorpus.run("full")`; `jobs.refresh` runs `run("refresh")` and refuses until `last_refresh` is set.
- **Router / chunking / session:** aliases; named Com. A `get_section` vs vigente (TO ∪ later A’s); serving uses structured chunker B on TO + clean A’s and fixed A otherwise; in-process session, one worker, `/clear`. Untouched.
- **Host-side refresh:** systemd oneshots + cron.d on the dump host (not GitHub Actions). Journal already captures stdout; this change also writes a file under `DATA_DIR`.

Constraints: Python 3.11+ via uv; structlog already on the job and API entrypoints (`configure_logging` in `logconfig.py` uses `PrintLoggerFactory` + JSON to stdout only). `IngestCorpus` currently emits no progress. `*.log` is gitignored. Chat `app.py` also calls `configure_logging()` in the same process family but must not start writing an ingest file.

## Goals / Non-Goals

**Goals:**

- Dual sink for ingest/refresh: stdout (console / journal) and a JSON file under `DATA_DIR/logs/`.
- `IngestCorpus` logs total for this run, the current document’s id/title/issue date, and processed count after each document including skips.
- Jobs pass the file path; the API process stays stdout-only.
- Unit tests cover sinks and progress fields. README Debug names both.

**Non-Goals (design-level):**

- Changing ports, fetch, extract, chunkers, MANIFEST, router, Gradio, or systemd units.
- Log rotation, log shipping, a ConsoleRenderer pretty-printer, or a new CLI flag.
- Injecting a logger port (structlog stays the process logger).

## Decisions

### Decision: stdlib factory, two handlers, JSON both sinks

Replace `PrintLoggerFactory` with `structlog.stdlib.LoggerFactory` and `ProcessorFormatter` + `JSONRenderer`. Handlers:

| Sink | When |
|---|---|
| `StreamHandler(sys.stdout)` | always (API and jobs) |
| `FileHandler(log_file, encoding="utf-8", delay=True)` | only when `configure_logging(log_file=...)` is passed |

`jobs.ingest` and `jobs.refresh` load Settings (via `build_ingest()`), then `configure_logging(log_file=settings.data_dir / "logs" / "ingest.log")` so the directory is created under the dump host `DATA_DIR`. Refresh uses the same file (one ingest-process log). Append; no rotation (a full CAMEX run is thousands of lines, not megabytes).

API keeps `configure_logging()` with no file. Use `logging.basicConfig(..., force=True)` so tests can reconfigure.

Alternatives: `print()` (breaks structured logs); a second logging library (YAGNI); ConsoleRenderer on stdout (nicer to watch, but splits formats and fights the existing JSON stdout contract). JSON on both sinks keeps grep/`jq` and the README story.

### Decision: Emit from `IngestCorpus`, wrap each document

Progress is a use-case concern, not Catalog/Extractor/Index. After the mode has filtered `documents`, log once:

- `ingest_run_started`: `mode`, `total` where `total = len(documents) + 1` (texto ordenado always considered).

Then wrap `_ingest_to` and each `_ingest_comunicacion`:

- before: `ingest_document_started` with `processed` (already finished this run), `total`, `doc_id`, `name`, `fecha` (ISO `fecha_emision` or `""`)
- after, including skip / non-PDF / non-BCRA early return: `ingest_document_finished` with `processed` incremented, same identity fields

TO identity: `doc_id=texto_ordenado`, `name="Exterior y Cambios"`, `fecha=""`. Comunicación A: `doc_id=comm_id` (e.g. `A13`), `name=title`, `fecha=fecha_emision.isoformat()`.

Do not log from `ChromaIndex` or the fetcher. Do not change checkpoint/skip logic; only observe it. Counters live in `run()`, so every `return` inside `_ingest_to` / `_ingest_comunicacion` still advances processed.

Alternatives: adapter-level logs (noisy, miss skips that never fetch); a progress callback port (hexagon bloat).

### Decision: Tests capture structlog and the file

New tests (same sitting as the code):

- `tests/test_logconfig.py`: with a `tmp_path` file, a log line appears on stdout **and** in the file as JSON with `event`, `level`, `timestamp`.
- `tests/test_ingest.py` (or a focused sibling): empty-dump full run of three catalog ids asserts `total == 4` before any upsert; A13 started/finished lines include `A13`, title CAMEX-1, `fecha=1981-03-02`; TO lines include `texto_ordenado` and Exterior y Cambios; a second run that skips unchanged ids still increments `processed` to `total`.

Use `structlog.testing.CapturingLoggerFactory` **or** configure the real dual sink against `tmp_path` and parse the file. Prefer the real sink for the file-survives-exit scenario. `src` coverage stays >= 80%.

### Decision: README Debug only, no new command

Update `## How to run` Debug: job logs are JSON on stdout **and** appended to `DATA_DIR/logs/ingest.log` (default `data/logs/ingest.log`). Extend `test_readme_operator_bullets`. Ingest/refresh module paths stay the same. systemd units unchanged (journal continues to show stdout).

### Decision: IBM 1–4 take/leave (unchanged)

| Take | Leave |
|---|---|
| Chroma on disk; upsert on refresh | LlamaIndex; GHA-hosted Chroma |
| Index owns embeddings | Extra EmbeddingsPort; FAISS second index |
| Structured dump + MANIFEST resume | Dated dump folders |
| Host crontab/compose/systemd for refresh | Recommender; GitHub-hosted vector index |

### Decision: Slip order

Never cut: progress total / processed / current document on ingest and refresh; dual sink; unit tests; README Debug.

Product slips that stay out: deontic scan (slip-first, design-only), log rotation, pretty console renderer, chat request logs in the same file.

## Risks / Trade-offs

- [API and jobs share `configure_logging`] → file handler is opt-in; API does not pass `log_file`.
- [Resume looks stuck if skips are silent] → finished counter increments on skip; started line still names the document.
- [Full-run `total` includes documents that will skip] → matches “this run will consider”, not “this run will download”; operators still see movement.
- [Log file grows across years of daily refresh] → append-only JSON lines; volume is small; rotation is out of scope (host logrotate later if needed).
- [`cache_logger_on_first_use` + tests] → `force=True` on stdlib config; tests configure before the use case logs.
- [JSON stdout is denser than a progress bar] → accepted; fields are greppable and match existing job logs.

## Migration Plan

No dump or index migration. Next `python -m bcra_rag.jobs.ingest` or `jobs.refresh` creates `DATA_DIR/logs/` and appends `ingest.log`. Rollback: revert the change; leftover log files may be deleted. Host deploy is the existing `./scripts/deploy.sh` (no unit file edits).

## Open Questions

None.
