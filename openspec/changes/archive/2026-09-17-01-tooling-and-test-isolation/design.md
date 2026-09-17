## Context

See proposal.md Why. Five ports stay five. No runtime module changes.

Facts as of this change's writing:
- `pyproject.toml:26-32` `[tool.hatch.build.targets.wheel.force-include]` lists `weblab.css`, `observatory.css`, `favicon.svg`, `favicon.png`, `og.png`, `guardrails/policy.yaml`. `src/bcra_rag/ui/` contains `apple-touch-icon.png favicon.ico favicon.svg observatory.css og.png weblab.css` (no `favicon.png`). `mount_ui` in `src/bcra_rag/ui/gradio_app.py` serves `/og.png`, `/favicon.svg`, `/apple-touch-icon.png`, `/weblab.css`, and passes `favicon_path=str(observatory_favicon_path())` (the `.ico`) to `gr.mount_gradio_app`.
- `pyproject.toml:69-75` ruff: `line-length = 100`, `select = ["E", "F", "I", "UP"]`, no per-file ignores. Errors: `src/bcra_rag/auth/mail_copy.py:77` (103 chars) and `:78` (126 chars) inside the OTP HTML template; `src/bcra_rag/auth/pages.py:73` (Google Fonts URL, 116 chars) and `:92` (footer `<p>`, 116 chars) inside the page template; `tests/test_ui.py:5-7` has `import pytest` / `import re` / `from fastapi import HTTPException` (stdlib `re` must move above `pytest`).
- `tests/features/live/http_client.py:45-57 load_live_dotenv(path=None)` reads `.env` and sets `os.environ[key] = value` for keys not already set. It is called by `live_base_url()`, `public_origin()`, `cookie_name()`, `require_imap_env()` in the same module, by `tests/prod/http_client.py:61,225`, and by `tests/prod/phoenix.py:45,53`. Unit tests `tests/test_live_http_client.py`, `tests/test_prod_http_client.py`, `tests/test_prod_phoenix.py` call those helpers with fakes, so `.env` leaks into the process; `tests/test_settings.py:41-63` then constructs `Settings(_env_file=None)` and asserts defaults that the leaked `MATOMO_URL`, `LLM_ENABLE_THINKING`, `DEFAULT_K`, … override.
- `tests/conftest.py:41-77 pytest_sessionstart` already branches on `--run-live-server` and `--run-prod-smoke` and imports the live helpers only there.

## Goals / Non-Goals

**Goals:**
- `uv sync` builds the editable wheel.
- `uv run ruff check .` exits 0 without touching template content.
- `uv run pytest -q` passes in any order with a populated `.env` in the repo root.
- Live and prod-smoke runs still get `.env` values (they need `LIVE_IMAP_*`, `LIVE_BASE_URL`, `PROD_BASE_URL`, `AUTH_PUBLIC_ORIGIN`).

**Non-Goals:**
- Rewriting the HTML templates to shorter lines.
- Adding `python-dotenv` to test dependencies.

## Decisions

### Decision: Fix the include list, do not drop it

Replace the `favicon.png` line with `favicon.ico` and `apple-touch-icon.png`. Alternative: delete the whole force-include block because `packages = ["src/bcra_rag"]` already ships package data — rejected as a wider behavioural change to packaging than this fix needs. A test parses `pyproject.toml` with `tomllib` and asserts each key `Path(key).is_file()` so a future rename fails fast.

### Decision: `per-file-ignores` for template modules, `--fix` for the import

```toml
[tool.ruff.lint.per-file-ignores]
"src/bcra_rag/auth/mail_copy.py" = ["E501"]
"src/bcra_rag/auth/pages.py" = ["E501"]
```
A `# noqa: E501` cannot be placed inside a triple-quoted string, and wrapping a URL breaks it. The `tests/test_ui.py` I001 is fixed by `uv run ruff check --fix tests/test_ui.py` (moves `import re` into the stdlib block).

### Decision: Opt-in flag on the dotenv loader

In `tests/features/live/http_client.py`:
```python
_DOTENV_ENABLED = False

def enable_live_dotenv() -> None:
    global _DOTENV_ENABLED
    _DOTENV_ENABLED = True

def load_live_dotenv(path: Path | None = None) -> None:
    if not _DOTENV_ENABLED and path is None:
        return
    ...existing body unchanged...
```
`path is None` keeps the explicit-path form usable by tests (they pass a `tmp_path` file). `tests/conftest.py::pytest_sessionstart` calls `enable_live_dotenv()` as the first statement of each of the two opt-in branches, before `resolved_base()` / `require_prod_ready()`. The three unit-test modules get an autouse fixture that forces the flag off (belt and braces if a future conftest change enables it globally):
```python
@pytest.fixture(autouse=True)
def _no_dotenv(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(http_client, "_DOTENV_ENABLED", False)
```
Alternative: `monkeypatch.delenv` for every key in `test_chat_settings_defaults` — rejected (papers over the leak; the next `.env` key breaks it again). Alternative: gate on `PYTEST_CURRENT_TEST` — rejected (implicit).

## Risks / Trade-offs

- [A live run forgets to enable the flag] → `pytest_sessionstart` is the single place; `scripts/run-prod-smoke.sh` already passes `--run-prod-smoke`; the live suite fails loudly on missing IMAP env (existing behaviour).
- [Someone re-adds a non-existent include] → `test_forced_includes_exist` fails.

## Migration Plan

None. Developer-only.

## Open Questions

None.
