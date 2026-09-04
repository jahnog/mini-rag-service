## Why

Cited CAMEX clauses with visible guardrails and L1 numbers need a process that does not ship new behavior untested. The constitution does not require unit tests for new functionality, a green suite, or an 80% `src` coverage floor.

## What Changes

Nothing is **BREAKING**. This change is docs and process (`skip_specs: true`).

- Add three short constitution lines in `openspec/config.yaml`: one `context` sentence, one `rules.tasks` line (replace the existing grouping line), one apply-guidance line (replace the L1 line, keep four bullets).
- Gate coverage in `[tool.coverage.report] fail_under = 80`. CI pytest runs the Reports coverage command; local Test stays `uv run pytest -q`.
- Reword README Test vs CI; one Reports line that coverage fails below 80%.
- Extend smoke tests so the constitution floor, `fail_under`, and CI `--cov=src` cannot silently disappear.
- Retarget sibling `bcra-mini-rag` coverage strings (tasks 1.5, 8.3, design slip item 5) so a later apply does not narrow the gate to domain/guardrails.

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
- Raising coverage of existing gaps (`jobs/ingest.py`, pdftotext extractor).
- Paid L1, Gherkin as a substitute for unit tests, Codecov upload, or a second coverage tool.
- Edits to sibling change `add-ingest-scripts`.
- An 80% requirement in the `platform` spec.

## Impact

- `openspec/config.yaml` (context, tasks rule, apply guidance).
- `pyproject.toml` coverage `fail_under`.
- `.github/workflows/test.yml` pytest coverage command.
- `README.md` Test vs CI wording and Reports 80% line.
- `tests/test_ci_workflow.py` and `tests/test_notes.py`.
- `openspec/changes/bcra-mini-rag/` tasks 1.5, 8.3 and design slip item 5.
- No runtime, API, dump, or index behavior change.
