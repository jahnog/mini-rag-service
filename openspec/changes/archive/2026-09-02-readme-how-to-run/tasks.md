## 1. Constitution

- [x] 1.1 Add the three constitution lines to `openspec/config.yaml` (one `context` sentence, one `rules.tasks` line, one apply-guidance line) and verify those strings are present in the file

## 2. README How to run

- [x] 2.1 Replace `## Ingest (this slice)` with `## How to run` (setup, build images, run, test, debug, ingest data, reports), keep the one-time vs refresh narrative and existing operator bullets, extend `test_readme_operator_bullets` for the heading and current commands, and verify `uv run pytest tests/test_notes.py tests/test_ci_workflow.py -q` passes
