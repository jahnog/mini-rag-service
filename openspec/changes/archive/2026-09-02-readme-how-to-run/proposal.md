## Why

Cited CAMEX clauses with visible guardrails and L1 numbers need a single operator/dev command index. README currently documents ingest only, and nothing in the OpenSpec constitution requires later command add/change/remove work to update it.

## What Changes

Nothing is **BREAKING**. This change is docs and process (`skip_specs: true`).

- Add a `## How to run` section to `README.md` covering the software development cycle (setup, build images, run, test, debug, ingest, reports).
- Replace `## Ingest (this slice)` so commands are not duplicated; keep the one-time vs refresh narrative inside Ingest data.
- Add three short constitution lines in `openspec/config.yaml`: one `context` sentence, one `rules.tasks` line, one apply-guidance line, so the same change that adds, changes, or removes a command updates that section.
- Extend the existing README smoke test so the heading and current command strings cannot silently disappear.

## Capabilities

### New Capabilities

- None. `skip_specs: true` — no spec-level behavior changes.

### Modified Capabilities

- None.

## Non-goals

- Banxico or any non-`bcra.gob.ar` corpus.
- Next.js v1.
- LlamaIndex.
- Redis.
- Filling the 1990–97 CAMEX catalog hole.
- GitHub-hosted vector index.
- Makefile / justfile / command wrappers.
- Chat API, L1 eval runner, or a debug compose service.
- Edits to sibling change `bcra-mini-rag`.

## Impact

- `openspec/config.yaml` (context, tasks rule, apply guidance).
- `README.md` operator/dev command index.
- `tests/test_notes.py` README asserts.
- No runtime, API, dump, or index behavior change.
