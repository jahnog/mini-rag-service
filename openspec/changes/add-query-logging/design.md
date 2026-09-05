## Context

See proposal.md Why and `specs/query-logging/spec.md` for the operator contract.

Product runtime already exists. Unchanged architecture (restated so this design satisfies the constitution):

- **Ports:** Catalog, Extractor, Index (owns embeddings), Llm, SessionStore. This change does not add a port.
- **Composition:** `build_ingest` / `build_app`; no DI container.
- **Ingest/refresh pipeline:** catalog → polite fetch → classify → extract → chunk A/B → index upsert → MANIFEST checkpoint. Jobs already dual-sink JSON to stdout and `DATA_DIR/logs/ingest.log`. Untouched.
- **Router / chunking / session:** aliases; named Com. A `get_section` vs vigente (TO ∪ later A’s); serving uses structured chunker B on TO + clean A’s and fixed A otherwise; in-process session, one worker, `/clear`. Untouched.
- **Host-side refresh:** systemd oneshots + cron.d on the dump host (not GitHub Actions). Journal already captures stdout.

Constraints: Python 3.11+ via uv; structlog JSON via `configure_logging` in `logconfig.py` (`LoggerFactory` + `ProcessorFormatter` + optional `FileHandler`). `*.log` is gitignored. Chat `app.py` currently calls `configure_logging()` with no file. `AnswerQuery` returns the v1 guardrail log on `ChatResponse` but does not emit a process log. `run_l1` overwrites `evals/l1.json` for the UI accordion.

## Goals / Non-Goals

**Goals:**

- Dual sink for completed chat turns: stdout and `DATA_DIR/logs/chat.log`.
- Dual sink for L1 published metrics: stdout and `DATA_DIR/logs/l1.log`, after the existing `evals/l1.json` write.
- Emit from the answering and L1 use cases so HTTP and Gradio share one record.
- Unit tests cover sinks and fields. README Debug names the files. No new command.

**Non-Goals (design-level):**

- Changing ports, fetch, extract, chunkers, MANIFEST, router, Gradio layout, systemd units, or `logconfig.py`.
- Log rotation, log shipping, a ConsoleRenderer, a logger port, or a new Settings key.
- Mixing chat/L1 into `ingest.log`.
- Per-gold-row L1 events, 401/429 lines, or LLM prompt logging.

## Decisions

### Decision: one file per process family

| Process | File | Event |
|---|---|---|
| API + Gradio (`bcra_rag.api.app`) | `DATA_DIR/logs/chat.log` | `chat_turn` |
| Operator L1 (`evals/run_l1.py`) | `DATA_DIR/logs/l1.log` | `l1_run` |
| Ingest / refresh | `DATA_DIR/logs/ingest.log` | unchanged |

`FileHandler(..., delay=True)` already creates the file on the first event, not at process start. Same as ingest. No synthetic startup line.

Alternatives: one shared `query.log` (interleaves two processes; fights ingest’s “one process family, one file”); append to `ingest.log` (proposal non-goal).

### Decision: emit from `AnswerQuery` and `run_l1`

`AnswerQuery.run` wraps the current body as `_respond` and logs once the `ChatResponse` exists. `_remember` stays inside `_respond` on the same paths as today (`/clear`, oversized, block, index-not-ready, llm-unavailable do not remember; empty-hits and success do).

```python
log.info(
    "chat_turn",
    message=request.message,
    k=request.k,
    filters=None if request.filters is None else request.filters.model_dump(),
    **response.model_dump(),
)
```

Pass dicts, never pydantic models. Do not log the LLM prompt, raw model body, or `_compose_followup` string. `session_id` ties follow-ups.

`run_l1` keeps writing `evals/l1.json`, then `log.info("l1_run", **payload)` with the published dict. No per-row events.

401/429 from `handle_turn` never produce a `ChatResponse`; skip them.

Alternatives: log in `handle_turn` (misses tests that call the use case; still misses 401/429); a logger port (hexagon bloat; ingest rejected this).

### Decision: API and L1 entrypoints pass the file path

`app.py` calls `configure_logging(log_file=Settings().data_dir / "logs" / "chat.log")` **before** `get_app()` so composition logs (if any) hit the same file. `evals/run_l1.py` calls `configure_logging(log_file=settings.data_dir / "logs" / "l1.log")` after loading Settings. `logconfig.py` is unchanged. Ingest jobs still pass `ingest.log`.

Replace `test_app_configures_logging_without_file` with a source assertion that `app.py` passes `chat.log` and does not mention `ingest.log`. Tests that assert file contents call `configure_logging` themselves.

Alternatives: a Settings field for the path (YAGNI; ingest inlines `data_dir / "logs" / ...`); configure after `get_app()` (Chroma init would miss the file).

### Decision: README Debug only, no new command

Update `## How to run` Debug: ingest stays on `DATA_DIR/logs/ingest.log`; chat turns append to `DATA_DIR/logs/chat.log`; an L1 operator run still overwrites `evals/l1.json` **and** appends the same metrics to `DATA_DIR/logs/l1.log`. Extend `test_readme_operator_bullets`. systemd units unchanged.

### Decision: IBM 1–4 take/leave (unchanged)

| Take | Leave |
|---|---|
| Chroma on disk; upsert on refresh | LlamaIndex; GHA-hosted Chroma |
| Index owns embeddings | Extra EmbeddingsPort; FAISS second index |
| Structured dump + MANIFEST resume | Dated dump folders |
| Host crontab/compose/systemd for refresh | Recommender; GitHub-hosted vector index |

### Decision: Slip order

Never cut: dual-sink `chat_turn` (query, answer, v1 guardrail log) and `l1_run` (published metrics); unit tests; README Debug.

Product slips that stay out: deontic scan (slip-first, design-only), log rotation, pretty console renderer, per-row L1, 401/429, LLM prompts.

## Risks / Trade-offs

- [Chat log contains full user questions] → dump-host file, gitignored `*.log`; same posture as ingest. Demo rate limit keeps volume small.
- [`ChatResponse.model_dump()` includes citation snippets] → snippets are already capped at 280 chars; dumping the public response avoids a second schema.
- [API `Settings()` is loaded twice (logging then `get_app`)] → same env; cheap. Logging must be configured first.
- [L1 payload nested dicts] → `JSONRenderer` already handles ingest fields of this shape; payload keys are JSON-safe.
- [Tests leak file handlers] → `configure_logging` already closes previous handlers on logger `bcra_rag`; tests that assert a file pass `log_file` themselves.
- [delay=True means no file until the first turn] → accepted; same as ingest; README names the path, not a startup probe.

## Migration Plan

No dump or index migration. Next API start creates `DATA_DIR/logs/chat.log` on the first completed turn. Next `uv run python evals/run_l1.py` creates `DATA_DIR/logs/l1.log` after writing `evals/l1.json`. Rollback: revert the change; leftover log files may be deleted. Host deploy is the existing `./scripts/deploy.sh` (no unit file edits).

## Open Questions

None.
