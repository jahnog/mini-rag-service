## Why

Cited CAMEX clauses with visible guardrails and L1 numbers. Today the developer tooling is broken in three small ways that block every later change: `uv sync` (and therefore plain `uv run …`) fails because `pyproject.toml` force-includes `src/bcra_rag/ui/favicon.png`, a file removed in commit `29cb1d3` (only `favicon.ico`, `favicon.svg`, `apple-touch-icon.png`, `og.png` exist); `uv run ruff check .` reports five pre-existing errors (E501 in two HTML-template modules, I001 in `tests/test_ui.py`); and `tests/test_settings.py::test_chat_settings_defaults` fails in the full default run (`AssertionError: assert 'https://…/Mat0mo/' == ''`) because `tests/features/live/http_client.py::load_live_dotenv` copies the developer's `.env` into `os.environ` whenever any live/prod helper is imported by a unit test.

## What Changes

- The wheel force-include list SHALL name only files that exist: `favicon.png` is removed; `favicon.ico` and `apple-touch-icon.png` (both served by `mount_ui`) are added. A unit test SHALL assert every forced include exists.
- Ruff SHALL pass on the whole tree: E501 is ignored per file for `src/bcra_rag/auth/mail_copy.py` and `src/bcra_rag/auth/pages.py` (long lines are inherent to their HTML/URL template strings); the import block of `tests/test_ui.py` is sorted.
- Reading the repository `.env` into the process environment SHALL happen only when the operator invoked `--run-live-server` or `--run-prod-smoke`. The default test command MUST NOT read `.env`. Existing helper signatures stay.

## Capabilities

### New Capabilities

- (none)

### Modified Capabilities

- `platform`: the default test command with fakes does not read the repository `.env`; packaging lists only existing static assets.
- `live-acceptance`: the live and production-smoke commands enable `.env` loading explicitly at session start.

## Non-goals

- Banxico or any non-`bcra.gob.ar` corpus.
- Next.js v1.
- LlamaIndex.
- Redis.
- Filling the 1990–97 CAMEX catalog hole.
- GitHub-hosted vector index.
- Reformatting the repository with `ruff format` (the gate is `ruff check`).
- Changing what `.env` keys the live suites use, or the auth/IMAP flow.
- Moving `load_live_dotenv` to `python-dotenv`.

## Impact

- `pyproject.toml` (force-include block; `[tool.ruff.lint.per-file-ignores]`).
- `tests/features/live/http_client.py` (module flag + `enable_live_dotenv()`), `tests/conftest.py` (`pytest_sessionstart`), autouse fixtures in `tests/test_live_http_client.py`, `tests/test_prod_http_client.py`, `tests/test_prod_phoenix.py`; `tests/test_ui.py` (import order + new packaging test).
- No runtime code path changes. `uv sync` works again; `uv run pytest -q` is order-independent. `src` coverage unaffected (tests only).
- No command added, changed, or removed; README `## How to run` unchanged.
