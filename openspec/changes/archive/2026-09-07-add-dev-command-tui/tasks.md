## 1. Catalog and loader

- [x] 1.1 Add `rich` to `[dependency-groups] dev` in `pyproject.toml`, run `uv lock`, and verify `uv run python -c "import rich"` works
- [x] 1.2 Write `scripts/commands.toml` with every How-to-run command (runnable uv/ssh/deploy.sh rows plus five `host = true` systemctl rows) and verify `scripts/devtui.py` load (once 1.3 exists) accepts it
- [x] 1.3 Implement catalog load in `scripts/devtui.py` (strict schema, argv allowlist, fence-line guards, `if __name__ == "__main__"`) and verify `uv run pytest tests/test_devtui.py -q` covers parse, duplicate id, unknown keys, allowlist equality, and injection rejects (`bash -c`, `python -c`, runnable `sudo`, fence ```` / `<!--`)

## 2. README sync

- [x] 2.1 Implement `--sync` / `--check` (mutually exclusive; fixed paths; no README symlink; normalized fence-line compare; temp `--sync` only) and verify tests sync a temp README, `--check` fails on missing/extra/stale markers, and pytest never `--sync`s the real `README.md`
- [x] 2.2 Update `README.md` `## How to run`: insert per-block markers, add the local-dev TUI launch fence under Setup (unmarked, contains `scripts/devtui.py`), run `--sync` once by hand, turn the inline systemctl list into the `systemctl` fence, and verify `uv run python scripts/devtui.py --check` exits 0 and `test_readme_operator_bullets` still passes

## 3. Picker and runner

- [x] 3.1 Implement the numbered Rich picker (markup off, skip `host = true`, `Prompt.ask` for q/empty/number, `Confirm` when `confirm`) and verify picker tests skip systemctl ids
- [x] 3.2 Implement the runner (`subprocess.run(..., shell=False)` vs `os.execvpe` for `tty`; ssh resolver + `--` host; deploy does not parse env; refuse `sudo` / `host = true`) and verify monkeypatched tests cover tty vs run, ssh injection refuses, deploy does not call the resolver, and `readme_line` is never executed

## 4. Arrow-key picker

- [x] 4.1 Add up/down (and j/k) highlight, Enter to run, digit jump, Selected command pane, and confirm-before-exec for destructive ids; verify `uv run pytest tests/test_devtui.py -q`

## 5. Verification

- [x] 5.1 Run `uv run pytest tests/test_devtui.py -q` then `uv run pytest -q` and `uv run pytest -q --cov=src --cov-report=term-missing --cov-report=xml`. Fix until green with src coverage >= 80%. No paid L1 eval.
