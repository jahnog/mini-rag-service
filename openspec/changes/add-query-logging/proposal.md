## Why

Cited CAMEX clauses with visible guardrails and L1 numbers are already returned on each chat turn and written to a static L1 results document, but they vanish from the dump host when the process exits: chat has no file sink, and each L1 run overwrites the last published numbers. Operators cannot reconstruct what was asked, what was answered, which v1 rule fired, or what an earlier L1 run scored.

## What Changes

Nothing is **BREAKING**.

- Every completed chat turn (HTTP, Gradio, `/clear`, oversized, blocked, silencio, in-corpus) is written to the process console and a dump-host log file: user message, structured answer, citation dump ids, and the full v1 guardrail log.
- A scope / injection / no-advice block is still logged, including the blocking rule.
- After an L1 run writes the static results document the UI already reads, the same published metrics are appended to the process console and a dump-host log file so a later overwrite does not erase the run.
- README `## How to run` Debug names the chat and L1 log files next to the existing ingest log (no new operator command).

## Capabilities

### New Capabilities

- `query-logging`: dump-host console and file records of each completed chat turn (query, answer, guardrail log) and of each L1 run’s published metrics.

### Modified Capabilities

- None. Existing query-answering, guardrails, evals-l1, and ingest-logging contracts stay; this change adds operator-visible persistence without changing those requirements.

## Non-goals

- Banxico or any non-`bcra.gob.ar` corpus.
- Next.js v1.
- LlamaIndex.
- Redis.
- Filling the 1990–97 CAMEX catalog hole.
- GitHub-hosted vector index.
- Mixing chat or L1 lines into the ingest log.
- Log rotation, log shipping, a log UI, or a pretty console renderer.
- Changing the HTTP chat contract, the UI trust panel, or the static L1 results document the accordion reads.
- Logging rate-limit or demo-key rejections, language-model prompts, or per-gold-row L1 lines.
- A new operator command or configuration key.

## Impact

- Chat answering emits one structured log event per completed turn; the API process gains a file sink beside stdout.
- The L1 use case emits one structured log event after writing the static results document; the operator L1 script gains a file sink.
- Log files live under the dump host `DATA_DIR` (ignored by git via `*.log`); they are not stored on GitHub.
- README Debug names the chat and L1 files. systemd units stay unchanged (journal still captures stdout).
- Unit tests cover both sinks. `src` coverage stays >= 80%.
- No new Python dependencies. No change to the five ports, composition graph, Gradio layout, or ingest jobs.
