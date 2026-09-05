## Context

See proposal.md for why. Product architecture is unchanged: five ports, composition root, ingest/refresh, router, chunking A/B, session memory, and host-side refresh stay as they are. IBM 1–4 take/leave and slip-first deontic scan are untouched.

Today every local-dev command lives as hand-written ````bash` fences under `README.md` `## How to run`, pinned by `tests/test_notes.py`. There is no Makefile, justfile, or `[project.scripts]` entry. Constraints: Python 3.11+ via uv; logic under `scripts/` so the wheel does not ship a developer toy; `src` coverage stays >= 80%; laptop/tests only.

## Goals / Non-Goals

**Goals:**

- One TOML catalog is the source of How-to-run command lines.
- A Rich numbered picker runs local-dev argv from that catalog.
- README fences inside `<!-- commands:<block> -->` markers are generated (`--sync` / `--check`) so the constitution index cannot drift.
- Exec is argv-list only, allowlisted, never `sudo`, never README placeholders.

**Non-Goals:**

- Product chat, Gradio, five-port changes.
- justfile / Textual / README-as-parser.
- Dump-host console, systemd, `sudo systemctl` from the picker.
- Dump-host console (systemctl from the picker).

## Decisions

1. **Catalog in `scripts/commands.toml`, not `src/`.** Hatch packages `bcra_rag` only. Tests load `scripts/devtui.py` via `importlib`. Alternative: a `bcra_rag.devtui` package — rejected (would ship in the wheel and need mypy/`src` coverage).

2. **README fences generated from TOML (`block` markers), TUI reads TOML only.** Alternative: parse README — rejected (fences mix captions, placeholders, and unfenced systemctl). Alternative: hand-edit both — rejected (drift). `block` (not one marker per `group`) keeps Deploy/Test captions next to the right fence.

3. **`readme_line` vs `argv`.** Documented deploy/ssh lines use `user@dump-host`. Runtime uses the operator env. Alternative: inject the example host — rejected (would SSH to a fake host).

4. **`host = true` is docs-only.** Five `sudo systemctl` rows still generate the README fence; the picker skips them; the runner refuses `argv[0] == "sudo"`. Alternative: omit them from TOML and leave a hand fence — rejected (`--check` would then allow a second unmarked fence). Alternative: execute them with confirm — rejected (laptop TUI is not a dump-host console).

5. **`needs_deploy_host` only on ssh-forward.** `deploy.sh` already sources `deploy/local.env`. Alternative: TUI also parses that file before deploy — rejected (two parsers disagree on `export DEPLOY_HOST=`). SSH host is appended as `["ssh", "-L", "8000:127.0.0.1:8000", "--", host]` after a strict regex; the TUI never `source`s the env file (line parse only, no interpolation).

6. **TTY picker: arrows + Enter + detail pane; number jump still works.** `Live(screen=False)` while reading keys (`termios` cbreak). Restore cooked attrs **before** `run_command` so Confirm, pytest, and `execvpe` (serve/pdb/ssh) get a normal TTY. Non-TTY falls back to `Prompt.ask`. Destructive catalog ids keep `confirm=true`; confirm text is title + `shlex.join(argv)`, never `readme_line`. Up/down never execute. `q` always quits.

7. **Exact argv allowlist** for `host = false` rows (the How-to-run `uv` / `ssh` / `./scripts/deploy.sh` shapes). A test pins TOML runnable tuples equal that set. `rich` is declared in the **dev** group (already pulled transitively by chromadb/typer).

8. **`--check` in pytest, not a new CI step.** Pytest never `--sync`s the real `README.md`. `--sync` / `--check` are mutually exclusive; no `--catalog` / `--cmd` flags.

## Risks / Trade-offs

- **[Risk]** Malicious `scripts/commands.toml` in a PR → **Mitigation:** load-time allowlist; no `shell=True`; fence lines cannot contain ```` or `<!--`; `sudo` never executed.
- **[Risk]** SSH option injection via `DEPLOY_HOST` → **Mitigation:** regex (no leading `-`, no metacharacters); host after `--`; never execute `readme_line`.
- **[Risk]** `--sync` writes the wrong file → **Mitigation:** fixed paths from `__file__`; refuse README symlink; temp file in `ROOT` then `os.replace`.
- **[Risk]** Stale README → **Mitigation:** `tests/test_devtui.py` `--check` on the real file; existing string pins in `test_readme_operator_bullets`.
- **[Trade-off]** Exact allowlist means every new command is TOML + one tuple. Accepted (reviewable, YAGNI for a generic runner).

## Migration Plan

No dump wipe, no index rebuild, no env key change. Rollback: remove `scripts/devtui.py` / `scripts/commands.toml` and restore README fences. `rich` in the dev group is unused if the script is gone.
