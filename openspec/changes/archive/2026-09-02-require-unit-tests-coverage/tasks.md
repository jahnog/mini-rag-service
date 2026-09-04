## 1. Constitution

- [x] 1.1 Add the three constitution lines to `openspec/config.yaml` (append Tests context sentence; replace the tasks grouping line with the unit-test MUST; replace the L1 apply-guidance line and keep four apply bullets) and verify those strings are present in the file

## 2. Coverage gate

- [x] 2.1 Set `[tool.coverage.report] fail_under = 80` in `pyproject.toml`, change CI pytest to `uv run pytest -q --cov=src --cov-report=term-missing --cov-report=xml`, reword README Test vs CI (Test stays `uv run pytest -q`; Reports keeps the coverage command and one line that it fails below 80%), extend `tests/test_ci_workflow.py` and `tests/test_notes.py` for those invariants, and verify `uv run pytest -q` plus the Reports command both pass with src coverage >= 80%

## 3. Sibling alignment

- [x] 3.1 Retarget `openspec/changes/bcra-mini-rag/` tasks 1.5 and 8.3 and design slip item 5 so the coverage gate is src >= 80% (CI already gates; do not narrow to domain/app/guardrails/chunkers) and verify those three strings no longer name that subset
