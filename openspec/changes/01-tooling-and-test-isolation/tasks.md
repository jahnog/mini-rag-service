# Tasks — 01 tooling and test isolation

Line anchors are as of this change's writing; if a line moved, grep the quoted symbol. Until task 1.1 lands, `uv run …` fails; use `.venv/bin/ruff`, `.venv/bin/pytest`, `.venv/bin/mypy` directly, or `uv run --no-sync …`.

## 1. platform — packaging

- [ ] 1.1 In `pyproject.toml`, block `[tool.hatch.build.targets.wheel.force-include]` (lines ~26-32): delete the line `"src/bcra_rag/ui/favicon.png" = "bcra_rag/ui/favicon.png"`; add, keeping alphabetical order within the block:
  ```toml
  "src/bcra_rag/ui/apple-touch-icon.png" = "bcra_rag/ui/apple-touch-icon.png"
  "src/bcra_rag/ui/favicon.ico" = "bcra_rag/ui/favicon.ico"
  ```
  Verify: `uv sync` → completes without `FileNotFoundError: Forced include not found`; `uv run python -c "import bcra_rag; print('ok')"` → `ok`.

- [ ] 1.2 In `tests/test_ui.py`, next to `test_page_images_are_served` (search `def test_page_images_are_served`), add:
  ```python
  def test_forced_includes_exist() -> None:
      import tomllib

      root = Path(__file__).resolve().parents[1]
      data = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))
      includes = data["tool"]["hatch"]["build"]["targets"]["wheel"]["force-include"]
      missing = [src for src in includes if not (root / src).is_file()]
      assert missing == []
      assert "src/bcra_rag/ui/favicon.ico" in includes
      assert "src/bcra_rag/ui/apple-touch-icon.png" in includes
  ```
  (`Path` is already imported at the top of the file.) Verify: `uv run pytest tests/test_ui.py::test_forced_includes_exist -q` → `1 passed`.

## 2. platform — ruff clean

- [ ] 2.1 In `pyproject.toml`, after the `[tool.ruff.lint]` table (`select = ["E", "F", "I", "UP"]`), add:
  ```toml
  [tool.ruff.lint.per-file-ignores]
  "src/bcra_rag/auth/mail_copy.py" = ["E501"]
  "src/bcra_rag/auth/pages.py" = ["E501"]
  ```
  Do not edit the two modules. Verify: `uv run ruff check src/bcra_rag/auth` → `All checks passed!`.

- [ ] 2.2 Run `uv run ruff check --fix tests/test_ui.py`. Expected diff: `import re` moves from below `import pytest` to the stdlib block (after `from pathlib import Path`). Verify: `uv run ruff check .` → `All checks passed!`.

## 3. live-acceptance — .env loading is opt-in

- [ ] 3.1 In `tests/features/live/http_client.py`, above `def load_live_dotenv` (line ~45), add a module flag and an enabler, and make the loader return early unless enabled or given an explicit path:
  ```python
  _DOTENV_ENABLED = False


  def enable_live_dotenv() -> None:
      """Allow load_live_dotenv() to read the repository .env (live/prod runs only)."""
      global _DOTENV_ENABLED
      _DOTENV_ENABLED = True


  def load_live_dotenv(path: Path | None = None) -> None:
      if path is None and not _DOTENV_ENABLED:
          return
      env_path = path or Path(".env")
      ...rest of the existing body unchanged...
  ```
  Verify: `uv run ruff check tests/features/live/http_client.py` → passes.

- [ ] 3.2 In `tests/conftest.py::pytest_sessionstart` (line ~41): inside `if session.config.getoption("--run-live-server"):` add as the first statements
  ```python
  from tests.features.live.http_client import enable_live_dotenv

  enable_live_dotenv()
  ```
  before the existing `from tests.features.live.http_client import live_base_url as resolved_base`. Inside `if session.config.getoption("--run-prod-smoke"):` add the same two lines before `from tests.features.live.http_client import require_imap_env`. Verify: `uv run ruff check tests/conftest.py` → passes.

- [ ] 3.3 Add an autouse fixture to each of `tests/test_live_http_client.py`, `tests/test_prod_http_client.py`, `tests/test_prod_phoenix.py` (place it right after the imports; add `from tests.features.live import http_client as live_http` to the imports if the module is not already imported under a name):
  ```python
  @pytest.fixture(autouse=True)
  def _no_dotenv(monkeypatch: pytest.MonkeyPatch) -> None:
      monkeypatch.setattr(live_http, "_DOTENV_ENABLED", False)
  ```
  Verify: `uv run pytest tests/test_live_http_client.py tests/test_prod_http_client.py tests/test_prod_phoenix.py -q` → all pass.

- [ ] 3.4 In `tests/test_live_http_client.py` add two tests:
  ```python
  def test_load_live_dotenv_is_noop_when_disabled(
      tmp_path: Path, monkeypatch: pytest.MonkeyPatch
  ) -> None:
      env = tmp_path / ".env"
      env.write_text("LIVE_DOTENV_PROBE=from-file\n", encoding="utf-8")
      monkeypatch.chdir(tmp_path)
      monkeypatch.delenv("LIVE_DOTENV_PROBE", raising=False)
      monkeypatch.setattr(live_http, "_DOTENV_ENABLED", False)
      live_http.load_live_dotenv()
      assert "LIVE_DOTENV_PROBE" not in os.environ


  def test_load_live_dotenv_loads_without_overriding_when_enabled(
      tmp_path: Path, monkeypatch: pytest.MonkeyPatch
  ) -> None:
      env = tmp_path / ".env"
      env.write_text("LIVE_DOTENV_PROBE=from-file\nLIVE_DOTENV_KEEP=from-file\n", encoding="utf-8")
      monkeypatch.chdir(tmp_path)
      monkeypatch.delenv("LIVE_DOTENV_PROBE", raising=False)
      monkeypatch.setenv("LIVE_DOTENV_KEEP", "from-shell")
      monkeypatch.setattr(live_http, "_DOTENV_ENABLED", False)
      live_http.enable_live_dotenv()
      try:
          live_http.load_live_dotenv()
      finally:
          live_http._DOTENV_ENABLED = False
      assert os.environ["LIVE_DOTENV_PROBE"] == "from-file"
      assert os.environ["LIVE_DOTENV_KEEP"] == "from-shell"
  ```
  Add `import os` and `from pathlib import Path` to the file's imports if missing. Verify: `uv run pytest tests/test_live_http_client.py -q` → all pass.

- [ ] 3.5 Order-dependency proof. With the developer `.env` present in the repo root run:
  `uv run pytest tests/test_live_http_client.py tests/test_prod_http_client.py tests/test_prod_phoenix.py tests/test_settings.py -q` → all pass (before this change, `test_chat_settings_defaults` fails here).

## 4. Gates

- [ ] 4.1 `uv run ruff check .` → `All checks passed!`; `uv run mypy src` → `Success: no issues found`; `uv run pytest -q --cov=src --cov-report=term-missing` → 0 failed, coverage ≥ 80%.
- [ ] 4.2 `uv run pytest --run-live-server -m live_server -q --collect-only` → collects without a `UsageError` about `.env` keys when the local process and IMAP are configured (skip this step if no local process is running; it is an operator check, not CI).
