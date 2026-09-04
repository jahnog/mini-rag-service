## Why

Cited CAMEX clauses with visible guardrails and L1 numbers need a living dump that can take many minutes (hundreds of Comunicaciones A plus the texto ordenado). One-time ingest and refresh already run, but they emit no progress: an operator cannot tell how many documents remain, how many this run has finished, or which document (date and name) is in flight. Console and file logs are needed now so a long job on the dump host is observable without attaching a debugger.

## What Changes

Nothing is **BREAKING**.

- One-time ingest and refresh (the shared ingest process) emit progress to **console and a log file**.
- At the start of a run, the operator can see **how many documents this run needs to process**.
- After each document, the operator can see **how many documents this run has already processed**.
- While a document is in flight, the operator can see its **issue date and name** (Comunicación A id plus title; texto ordenado uses its dump id and official name).
- Unchanged / skipped documents still advance the processed count so a resume does not look stuck.
- README `## How to run` Debug names the console and the log file (no new operator command).

Assumptions recorded: “ingest process” means both `jobs.ingest` and `jobs.refresh` because they share the same pipeline. “Date” is the document’s `fecha_emision` (ISO) when the catalog has one; the log event also carries a timestamp. “Name” is the Comunicación A id plus title, or `texto_ordenado` plus the Exterior y Cambios label.

## Capabilities

### New Capabilities

- `ingest-logging`: one-time ingest and refresh emit console and file progress so an operator can see how many documents this run needs to process, how many it has already processed, and the date and name of the document currently in flight.

### Modified Capabilities

- None. Existing corpus-ingest catalog, texto ordenado, resume, and refresh contracts stay; this change adds operator-visible progress without changing those requirements.

## Non-goals

- Banxico or any non-`bcra.gob.ar` corpus.
- Next.js v1.
- LlamaIndex.
- Redis.
- Filling the 1990–97 CAMEX catalog hole.
- GitHub-hosted vector index.
- Changing catalog, fetch, extract, chunk, index upsert, or MANIFEST checkpoint behavior.
- A log UI, log shipping, structured log aggregation, or systemd journal configuration.
- Chat, Gradio, L1 evals, query guardrails, or session memory.

## Impact

- Ingest/refresh job entrypoints and the shared ingest use case emit progress; logging configuration gains a file sink beside existing stdout.
- Log files live under the dump host `DATA_DIR` (ignored by git via `*.log`); they are not stored on GitHub.
- README Debug line that currently says job logs are JSON on stdout is updated to mention the file as well.
- Unit tests cover the progress fields and both sinks. `src` coverage stays >= 80%.
- No new Python dependencies. No change to the five ports, composition graph, chat API, or Gradio UI.
