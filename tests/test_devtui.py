from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[1]


def load_devtui() -> Any:
    spec = importlib.util.spec_from_file_location("devtui", ROOT / "scripts" / "devtui.py")
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    sys.modules["devtui"] = mod
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture
def devtui() -> Any:
    return load_devtui()


def _row(**overrides: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "id": "unit",
        "group": "Test",
        "block": "test-unit",
        "title": "Unit tests",
        "summary": "fakes",
        "argv": ["uv", "run", "pytest", "-q"],
    }
    base.update(overrides)
    return base


def test_real_catalog_parses_and_matches_allowlist(devtui: Any) -> None:
    cmds = devtui.load_catalog()
    ids = {c.id for c in cmds}
    for required in (
        "sync",
        "serve",
        "unit",
        "pdb",
        "ingest",
        "refresh",
        "coverage",
        "l1",
        "deploy",
        "ssh-forward",
        "unit-start",
    ):
        assert required in ids
    runnable = {c.argv for c in cmds if not c.host}
    assert runnable == devtui.ALLOWED_RUNNABLE
    assert all(c.host for c in cmds if c.argv[0] == "sudo")
    picker = [c.id for c in devtui.runnable_commands(cmds)]
    assert "unit-start" not in picker
    assert "unit" in picker


def test_duplicate_id_fails(devtui: Any) -> None:
    row = _row()
    with pytest.raises(devtui.CatalogError, match="duplicate"):
        cmds = [
            devtui.command_from_table(row, root=ROOT),
            devtui.command_from_table(row, root=ROOT),
        ]
        ids = [c.id for c in cmds]
        if len(ids) != len(set(ids)):
            raise devtui.CatalogError("duplicate command id")


def test_unknown_key_fails(devtui: Any) -> None:
    with pytest.raises(devtui.CatalogError, match="unknown keys"):
        devtui.command_from_table(_row(env={"X": "1"}), root=ROOT)


def test_fence_renderer_uses_readme_line(devtui: Any) -> None:
    cmd = devtui.command_from_table(
        _row(
            id="deploy",
            group="Deploy",
            block="deploy",
            title="Deploy",
            argv=["./scripts/deploy.sh"],
            readme_line="DEPLOY_HOST=user@dump-host ./scripts/deploy.sh",
            confirm=True,
        ),
        root=ROOT,
    )
    assert cmd.fence_line() == "DEPLOY_HOST=user@dump-host ./scripts/deploy.sh"


def test_injection_argv_rejected(devtui: Any) -> None:
    with pytest.raises(devtui.CatalogError):
        devtui.command_from_table(
            _row(argv=["bash", "-c", "touch /tmp/pwn"]), root=ROOT
        )
    with pytest.raises(devtui.CatalogError):
        devtui.command_from_table(
            _row(argv=["uv", "run", "python", "-c", "print(1)"]), root=ROOT
        )
    with pytest.raises(devtui.CatalogError, match="sudo"):
        devtui.command_from_table(
            _row(argv=["sudo", "id"]), root=ROOT
        )
    with pytest.raises(devtui.CatalogError):
        devtui.command_from_table(
            _row(argv=["ssh", "-L", "8000:127.0.0.1:8000", "-oProxyCommand=x"]),
            root=ROOT,
        )
    with pytest.raises(devtui.CatalogError):
        devtui.command_from_table(
            _row(
                argv=["./scripts/../.git/hooks/x"],
            ),
            root=ROOT,
        )
    with pytest.raises(devtui.CatalogError, match="<!--"):
        devtui.command_from_table(
            _row(readme_line="uv sync <!--"),
            root=ROOT,
        )
    with pytest.raises(devtui.CatalogError):
        devtui.command_from_table(
            _row(readme_line="uv sync ```"),
            root=ROOT,
        )


def test_docs_only_systemctl_shape(devtui: Any) -> None:
    cmd = devtui.command_from_table(
        _row(
            id="unit-start",
            group="Deploy",
            block="systemctl",
            title="Start",
            argv=["sudo", "systemctl", "start", "bcra-rag"],
            host=True,
        ),
        root=ROOT,
    )
    assert cmd.host
    with pytest.raises(devtui.CatalogError):
        devtui.command_from_table(
            _row(
                id="unit-start",
                group="Deploy",
                block="systemctl",
                title="Start",
                argv=["sudo", "id"],
                host=True,
            ),
            root=ROOT,
        )


def test_run_sh_execs_tui() -> None:
    path = ROOT / "run.sh"
    text = path.read_text(encoding="utf-8")
    assert text.startswith("#!/usr/bin/env bash")
    assert "set -euo pipefail" in text
    assert 'exec uv run python scripts/devtui.py "$@"' in text
    assert path.stat().st_mode & 0o111


def test_check_real_readme(devtui: Any) -> None:
    cmds = devtui.load_catalog()
    devtui.check_readme(cmds)
    assert devtui.main(["--check"]) == 0


def test_sync_and_check_temp_readme(devtui: Any, tmp_path: Path) -> None:
    cmds = devtui.load_catalog()
    readme = tmp_path / "README.md"
    readme.write_text(
        ROOT.joinpath("README.md").read_text(encoding="utf-8"), encoding="utf-8"
    )
    stale = readme.read_text(encoding="utf-8").replace("uv sync", "uv sync --no-dev", 1)
    readme.write_text(stale, encoding="utf-8")
    with pytest.raises(devtui.CatalogError, match="stale"):
        devtui.check_readme(cmds, readme_path=readme)
    devtui.sync_readme(cmds, readme_path=readme, root=tmp_path)
    devtui.check_readme(cmds, readme_path=readme)


def test_sync_refuses_symlink_readme(devtui: Any, tmp_path: Path) -> None:
    cmds = devtui.load_catalog()
    real = tmp_path / "real.md"
    real.write_text("# x\n\n## How to run\n\n", encoding="utf-8")
    link = tmp_path / "README.md"
    link.symlink_to(real)
    with pytest.raises(devtui.CatalogError, match="symlink"):
        devtui.sync_readme(cmds, readme_path=link, root=tmp_path)


def test_missing_marker_fails_check(devtui: Any, tmp_path: Path) -> None:
    cmds = devtui.load_catalog()
    readme = tmp_path / "README.md"
    text = ROOT.joinpath("README.md").read_text(encoding="utf-8")
    text = text.replace("<!-- commands:setup -->\n", "").replace(
        "<!-- /commands:setup -->\n", ""
    )
    readme.write_text(text, encoding="utf-8")
    with pytest.raises(devtui.CatalogError, match="mismatch"):
        devtui.check_readme(cmds, readme_path=readme)


def test_runner_tty_vs_subprocess(devtui: Any) -> None:
    cmds = {c.id: c for c in devtui.load_catalog()}
    calls: list[Any] = []

    def fake_run(argv: Any, **kwargs: Any) -> SimpleNamespace:
        calls.append(("run", list(argv), kwargs.get("shell"), kwargs.get("cwd")))
        return SimpleNamespace(returncode=0)

    def fake_exec(file: str, argv: Any, env: Any) -> None:
        calls.append(("exec", file, list(argv)))
        raise OSError("no exec in tests")

    code = devtui.run_command(cmds["unit"], run_fn=fake_run, execvpe_fn=fake_exec)
    assert code == 0
    assert calls[0][0] == "run"
    assert calls[0][1] == ["uv", "run", "pytest", "-q"]
    assert calls[0][2] is False

    chdir_to: list[Path] = []
    with pytest.raises(OSError, match="no exec"):
        devtui.run_command(
            cmds["serve"],
            run_fn=fake_run,
            execvpe_fn=fake_exec,
            chdir_fn=chdir_to.append,
        )
    assert calls[-1][0] == "exec"
    assert chdir_to == [devtui.ROOT]


def test_runner_refuses_host_and_sudo(devtui: Any) -> None:
    cmds = {c.id: c for c in devtui.load_catalog()}
    ran: list[Any] = []

    def fake_run(*args: Any, **kwargs: Any) -> SimpleNamespace:
        ran.append(1)
        return SimpleNamespace(returncode=0)

    with pytest.raises(devtui.CatalogError, match="dump-host"):
        devtui.run_command(cmds["unit-start"], run_fn=fake_run)
    assert ran == []


def test_deploy_does_not_resolve_host(devtui: Any) -> None:
    cmds = {c.id: c for c in devtui.load_catalog()}
    seen: list[Any] = []

    def fake_run(argv: Any, **kwargs: Any) -> SimpleNamespace:
        seen.append(list(argv))
        return SimpleNamespace(returncode=0)

    code = devtui.run_command(
        cmds["deploy"],
        environ={},
        confirm_fn=lambda _line: True,
        run_fn=fake_run,
    )
    assert code == 0
    assert seen == [["./scripts/deploy.sh"]]


def test_ssh_appends_validated_host(devtui: Any, tmp_path: Path) -> None:
    cmds = {c.id: c for c in devtui.load_catalog()}
    seen: list[Any] = []

    def fake_exec(file: str, argv: Any, env: Any) -> None:
        seen.append(list(argv))
        raise OSError("stop")

    with pytest.raises(OSError):
        devtui.run_command(
            cmds["ssh-forward"],
            environ={"DEPLOY_HOST": "alice@dump-host"},
            confirm_fn=lambda _line: True,
            execvpe_fn=fake_exec,
            chdir_fn=lambda _p: None,
            local_env_path=tmp_path / "missing.env",
        )
    assert seen == [["ssh", "-L", "8000:127.0.0.1:8000", "--", "alice@dump-host"]]


@pytest.mark.parametrize(
    "bad",
    [
        "-oProxyCommand=touch /tmp/pwn",
        "host; id",
        "user@host -R 1:1",
        "",
        "alice@dump-host\n",
        "user@dump-host=$(id)",
    ],
)
def test_ssh_rejects_bad_deploy_host(devtui: Any, tmp_path: Path, bad: str) -> None:
    cmds = {c.id: c for c in devtui.load_catalog()}
    ran: list[Any] = []

    def fake_exec(*args: Any, **kwargs: Any) -> None:
        ran.append(1)

    with pytest.raises(devtui.CatalogError):
        devtui.run_command(
            cmds["ssh-forward"],
            environ={"DEPLOY_HOST": bad},
            confirm_fn=lambda _line: True,
            execvpe_fn=fake_exec,
            chdir_fn=lambda _p: None,
            local_env_path=tmp_path / "nope.env",
        )
    assert ran == []


def test_local_env_host_parse_no_source(devtui: Any, tmp_path: Path) -> None:
    env_file = tmp_path / "local.env"
    env_file.write_text(
        "# comment\nOTHER=1\nDEPLOY_HOST=bob@dump-host\n", encoding="utf-8"
    )
    host = devtui.resolve_deploy_host({}, env_file)
    assert host == "bob@dump-host"
    evil = tmp_path / "evil.env"
    evil.write_text("DEPLOY_HOST=$(id)\n", encoding="utf-8")
    with pytest.raises(devtui.CatalogError):
        devtui.resolve_deploy_host({}, evil)


def test_readme_line_is_never_executed(devtui: Any) -> None:
    cmds = {c.id: c for c in devtui.load_catalog()}
    seen: list[Any] = []

    def fake_run(argv: Any, **kwargs: Any) -> SimpleNamespace:
        seen.append(list(argv))
        return SimpleNamespace(returncode=0)

    devtui.run_command(cmds["deploy"], confirm_fn=lambda _line: True, run_fn=fake_run)
    assert seen[0] == ["./scripts/deploy.sh"]
    assert "user@dump-host" not in seen[0]


def test_confirm_false_skips_run(devtui: Any) -> None:
    cmds = {c.id: c for c in devtui.load_catalog()}
    ran: list[Any] = []

    def fake_run(*args: Any, **kwargs: Any) -> SimpleNamespace:
        ran.append(1)
        return SimpleNamespace(returncode=0)

    assert (
        devtui.run_command(cmds["ingest"], confirm_fn=lambda _line: False, run_fn=fake_run)
        == 0
    )
    assert ran == []


def test_move_index_wraps(devtui: Any) -> None:
    assert devtui.move_index(0, -1, 16) == 15
    assert devtui.move_index(15, 1, 16) == 0
    assert devtui.move_index(7, 1, 16) == 8


def test_handle_key_arrows_enter_quit_and_jump(devtui: Any) -> None:
    n = 16
    state = devtui.PickerState(0)
    state, action = devtui.handle_key(state, "down", n)
    assert action == "redraw" and state.index == 1 and state.digits == ""
    state, action = devtui.handle_key(devtui.PickerState(0), "up", n)
    assert action == "redraw" and state.index == 15
    state, action = devtui.handle_key(devtui.PickerState(3), "enter", n)
    assert action == "run" and state.index == 3
    state, action = devtui.handle_key(devtui.PickerState(0, "8"), "enter", n)
    assert action == "run" and state.index == 7
    state, action = devtui.handle_key(devtui.PickerState(2, "1"), "quit", n)
    assert action == "quit"
    state, action = devtui.handle_key(devtui.PickerState(4, "8"), "down", n)
    assert action == "redraw" and state.index == 5 and state.digits == ""
    state, action = devtui.handle_key(devtui.PickerState(0, "99"), "enter", n)
    assert action == "redraw" and state.index == 0 and state.digits == ""
    state, action = devtui.handle_key(devtui.PickerState(0, "1"), "esc", n)
    assert action == "redraw" and state.digits == ""


def test_read_key_arrows_and_digits(devtui: Any) -> None:
    def from_seq(seq: str) -> str:
        buf = list(seq)

        def read1() -> str:
            return buf.pop(0)

        return devtui.read_key(read1=read1, wait=lambda _t: bool(buf))

    assert from_seq("\x1b[A") == "up"
    assert from_seq("\x1b[B") == "down"
    assert from_seq("\x1bOA") == "up"
    assert from_seq("\x1bOB") == "down"
    assert devtui.read_key(read1=lambda: "8", wait=lambda _t: False) == "digit:8"
    assert devtui.read_key(read1=lambda: "\r", wait=lambda _t: False) == "enter"
    assert devtui.read_key(read1=lambda: "q", wait=lambda _t: False) == "quit"


def test_detail_text_is_command_line(devtui: Any) -> None:
    cmds = {c.id: c for c in devtui.load_catalog()}
    assert devtui.detail_text(cmds["unit"]) == "uv run pytest -q"
    assert "command:" not in devtui.detail_text(cmds["ssh-forward"])


def test_destructive_ids_require_confirm(devtui: Any) -> None:
    cmds = {c.id: c for c in devtui.load_catalog()}
    for ident in devtui.DESTRUCTIVE_IDS:
        assert cmds[ident].confirm is True
    for ident in ("unit", "coverage", "sync"):
        assert cmds[ident].confirm is False


def test_confirm_prompt_uses_argv_not_placeholder(devtui: Any) -> None:
    cmds = {c.id: c for c in devtui.load_catalog()}
    text = devtui.confirm_prompt_text(cmds["deploy"])
    assert "user@dump-host" not in text
    assert "./scripts/deploy.sh" in text
    seen: list[str] = []

    def confirm(msg: str) -> bool:
        seen.append(msg)
        return False

    ran: list[Any] = []

    def fake_run(*args: Any, **kwargs: Any) -> SimpleNamespace:
        ran.append(1)
        return SimpleNamespace(returncode=0)

    assert (
        devtui.run_command(cmds["deploy"], confirm_fn=confirm, run_fn=fake_run) == 0
    )
    assert ran == []
    assert seen and "user@dump-host" not in seen[0]


def test_picker_skips_host_rows(devtui: Any) -> None:
    cmds = devtui.load_catalog()
    picked: list[str] = []

    def prompt(_msg: str) -> str:
        return "q"

    def fake_run(*args: Any, **kwargs: Any) -> SimpleNamespace:
        picked.append("ran")
        return SimpleNamespace(returncode=0)

    assert devtui.pick_and_run(cmds, prompt_fn=prompt, run_fn=fake_run) == 0
    assert [c.id for c in devtui.runnable_commands(cmds)] == [
        c.id for c in cmds if not c.host
    ]
    assert picked == []


def test_main_rejects_sync_and_check_together(devtui: Any) -> None:
    with pytest.raises(SystemExit):
        devtui.main(["--sync", "--check"])


def test_main_unknown_flag(devtui: Any) -> None:
    with pytest.raises(SystemExit):
        devtui.main(["--cmd", "uv sync"])
