## Why

Cited CAMEX clauses with visible guardrails and L1 numbers still need a local way to run the How-to-run cycle without grepping `README.md`. Operators forget `uv run` variants for test, debug, ingest, coverage, and deploy.

## What Changes

Nothing is **BREAKING**. This change is local-dev tooling and docs (`skip_specs: true`).

- Add a Rich numbered picker (`uv run python scripts/devtui.py`) that lists local-dev/test commands from `scripts/commands.toml` and runs the selected argv (TTY commands replace the process).
- Generate `README.md` `## How to run` command fences from that catalog (`--sync` / `--check`) so the documented index cannot drift.
- Dump-host `sudo systemctl …` stays in the README catalog as docs-only rows; the picker never executes them. The TUI is laptop/tests only — not a dump-host or production console.
- `rich` is declared in the uv dev group.

## Capabilities

### New Capabilities

- None. `skip_specs: true` — no spec-level behavior changes (not product chat, not the Gradio observatory).

### Modified Capabilities

- None.

## Non-goals

- Banxico or any non-`bcra.gob.ar` corpus.
- Next.js v1.
- LlamaIndex.
- Redis.
- Filling the 1990–97 CAMEX catalog hole.
- GitHub-hosted vector index.
- Gradio / observatory changes.
- justfile, Makefile, Textual, parsing README as the TUI catalog.
- `[project.scripts]` entry point, systemd unit, cron, or dump-host operator console.
- Auto-running ingest/deploy; executing README placeholder hosts; `sudo` from the picker.

## Impact

- `scripts/commands.toml` (catalog), `scripts/devtui.py` (picker + README sync).
- `README.md` `## How to run` (markers, generated fences, TUI launch line).
- `pyproject.toml` / `uv.lock` (`rich` in the dev group).
- `tests/test_devtui.py` (catalog, sync check, runner fakes, injection cases).
- Existing `test_readme_operator_bullets` still pins command strings.
- No runtime, API, dump, or index behavior change.
