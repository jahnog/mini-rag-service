"""Local-dev command TUI. Laptop / tests only — not for the dump host."""

from __future__ import annotations

import argparse
import os
import re
import shlex
import subprocess
import sys
import tempfile
import tomllib
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

Action = Literal["run", "quit", "redraw"]

SCRIPT_DIR = Path(__file__).resolve().parent
ROOT = SCRIPT_DIR.parent
CATALOG_PATH = SCRIPT_DIR / "commands.toml"
README_PATH = ROOT / "README.md"
LOCAL_ENV_PATH = ROOT / "deploy" / "local.env"

GROUPS = ("Setup", "Run", "Deploy", "Test", "Debug", "Ingest", "Reports")
KNOWN_KEYS = frozenset(
    {
        "id",
        "group",
        "block",
        "title",
        "summary",
        "argv",
        "readme_line",
        "tty",
        "confirm",
        "host",
        "needs_deploy_host",
    }
)
ID_RE = re.compile(r"^[a-z0-9-]+$")
HOST_NAME_RE = re.compile(
    r"^[A-Za-z0-9][A-Za-z0-9._-]*(?:@[A-Za-z0-9][A-Za-z0-9._-]*)?$"
)
HOST_IPV4_RE = re.compile(
    r"^(?:[A-Za-z0-9][A-Za-z0-9._-]*@)?\d{1,3}(?:\.\d{1,3}){3}$"
)
HOST_BAD = re.compile(r"[\s$`;&|<>:=\x00]")
SYSTEMCTL_VERBS = frozenset({"start", "stop", "status"})
SYSTEMCTL_UNITS = frozenset({"bcra-rag", "bcra-rag-ingest", "bcra-rag-refresh"})
SSH_ARGV = ("ssh", "-L", "8000:127.0.0.1:8000")
ALLOWED_RUNNABLE: frozenset[tuple[str, ...]] = frozenset(
    {
        ("uv", "sync"),
        (
            "uv",
            "run",
            "uvicorn",
            "bcra_rag.api.app:app",
            "--host",
            "0.0.0.0",
            "--port",
            "8000",
        ),
        ("uv", "run", "ruff", "check", "."),
        ("uv", "run", "mypy", "src"),
        ("uv", "run", "pytest", "-q"),
        ("uv", "run", "pytest", "--pdb"),
        ("uv", "run", "pytest", "--run-integration", "-m", "integration", "-q"),
        (
            "uv",
            "run",
            "pytest",
            "--run-integration",
            "tests/test_jobs_integration.py::test_ingest_command_downloads_one_real_pdf",
            "-q",
        ),
        (
            "uv",
            "run",
            "pytest",
            "--run-integration",
            "tests/test_jobs_integration.py::test_refresh_command_downloads_one_real_pdf",
            "-q",
        ),
        (
            "uv",
            "run",
            "pytest",
            "-q",
            "--cov=src",
            "--cov-report=term-missing",
            "--cov-report=xml",
        ),
        ("uv", "run", "python", "-m", "bcra_rag.jobs.ingest"),
        ("uv", "run", "python", "-m", "bcra_rag.jobs.refresh"),
        ("uv", "run", "python", "evals/run_l1.py"),
        ("./scripts/deploy.sh",),
        ("./scripts/deploy.sh", "--ingest"),
        SSH_ARGV,
    }
)
MARKER_PAIR = re.compile(
    r"<!-- commands:([a-z0-9-]+) -->\n(.*?)<!-- /commands:\1 -->",
    re.S,
)
BASH_FENCE = re.compile(r"```bash\n(.*?)```", re.S)
HOW_TO_HEAD = re.compile(r"^## How to run\s*$", re.M)
NEXT_H2 = re.compile(r"^## ", re.M)


class CatalogError(ValueError):
    """Invalid catalog, README markers, or host value."""


@dataclass(frozen=True)
class Command:
    id: str
    group: str
    block: str
    title: str
    summary: str
    argv: tuple[str, ...]
    readme_line: str | None
    tty: bool
    confirm: bool
    host: bool
    needs_deploy_host: bool

    def fence_line(self) -> str:
        if self.readme_line is not None:
            return self.readme_line
        return shlex.join(self.argv)


def _as_bool(value: Any, key: str) -> bool:
    if isinstance(value, bool):
        return value
    raise CatalogError(f"{key} must be a boolean")


def _check_fence_line(line: str) -> None:
    if not line or "\n" in line or "\r" in line:
        raise CatalogError("fence line must be a single non-empty line")
    if "```" in line or "<!--" in line:
        raise CatalogError("fence line must not contain ``` or <!--")


def _check_argv_strings(argv: Any) -> tuple[str, ...]:
    if not isinstance(argv, list) or not argv:
        raise CatalogError("argv must be a non-empty list of strings")
    out: list[str] = []
    for item in argv:
        if not isinstance(item, str) or item == "":
            raise CatalogError("argv elements must be non-empty strings")
        if "\0" in item or "\n" in item or "\r" in item:
            raise CatalogError("argv elements must not contain NUL or newlines")
        out.append(item)
    return tuple(out)


def _check_deploy_script(root: Path) -> None:
    script = root / "scripts" / "deploy.sh"
    if script.is_symlink():
        raise CatalogError("scripts/deploy.sh must not be a symlink")
    if not script.is_file():
        raise CatalogError("scripts/deploy.sh is missing")
    if script.resolve() != (root / "scripts" / "deploy.sh").resolve():
        raise CatalogError("scripts/deploy.sh path escaped scripts/")


def command_from_table(raw: Mapping[str, Any], *, root: Path) -> Command:
    extra = set(raw) - KNOWN_KEYS
    if extra:
        raise CatalogError(f"unknown keys: {sorted(extra)}")
    for key in ("id", "group", "block", "title", "argv"):
        if key not in raw:
            raise CatalogError(f"missing {key}")
    ident = raw["id"]
    group = raw["group"]
    block = raw["block"]
    title = raw["title"]
    if not isinstance(ident, str) or not ID_RE.fullmatch(ident):
        raise CatalogError("id must match ^[a-z0-9-]+$")
    if group not in GROUPS:
        raise CatalogError(f"invalid group: {group!r}")
    if not isinstance(block, str) or not ID_RE.fullmatch(block):
        raise CatalogError("block must match ^[a-z0-9-]+$")
    if not isinstance(title, str) or not title:
        raise CatalogError("title must be a non-empty string")
    summary = raw.get("summary", "")
    if not isinstance(summary, str):
        raise CatalogError("summary must be a string")
    argv = _check_argv_strings(raw["argv"])
    readme_line = raw.get("readme_line")
    if readme_line is not None:
        if not isinstance(readme_line, str):
            raise CatalogError("readme_line must be a string")
        _check_fence_line(readme_line)
    tty = _as_bool(raw.get("tty", False), "tty")
    confirm = _as_bool(raw.get("confirm", False), "confirm")
    host = _as_bool(raw.get("host", False), "host")
    needs_deploy_host = _as_bool(raw.get("needs_deploy_host", False), "needs_deploy_host")
    if host:
        if needs_deploy_host or tty:
            raise CatalogError("docs-only rows cannot set tty or needs_deploy_host")
        if (
            len(argv) != 4
            or argv[0] != "sudo"
            or argv[1] != "systemctl"
            or argv[2] not in SYSTEMCTL_VERBS
            or argv[3] not in SYSTEMCTL_UNITS
        ):
            raise CatalogError("docs-only argv must be sudo systemctl <verb> <unit>")
    else:
        if argv[0] == "sudo":
            raise CatalogError("sudo is not in the exec allowlist")
        if argv not in ALLOWED_RUNNABLE:
            raise CatalogError(f"argv not allowlisted: {argv!r}")
        if argv[0] == "./scripts/deploy.sh":
            _check_deploy_script(root)
        if needs_deploy_host and argv != SSH_ARGV:
            raise CatalogError("needs_deploy_host is only valid for ssh-forward")
    cmd = Command(
        id=ident,
        group=group,
        block=block,
        title=title,
        summary=summary,
        argv=argv,
        readme_line=readme_line,
        tty=tty,
        confirm=confirm,
        host=host,
        needs_deploy_host=needs_deploy_host,
    )
    _check_fence_line(cmd.fence_line())
    return cmd


def load_catalog(
    path: Path | None = None, *, root: Path | None = None
) -> list[Command]:
    catalog_path = path if path is not None else CATALOG_PATH
    repo = root if root is not None else ROOT
    expected_catalog = (repo / "scripts" / "commands.toml").resolve()
    if catalog_path.resolve() != expected_catalog:
        raise CatalogError("catalog path must be <root>/scripts/commands.toml")
    raw = tomllib.loads(catalog_path.read_text(encoding="utf-8"))
    rows = raw.get("command")
    if not isinstance(rows, list) or not rows:
        raise CatalogError("catalog must have [[command]] rows")
    cmds = [command_from_table(row, root=repo) for row in rows]
    ids = [c.id for c in cmds]
    if len(ids) != len(set(ids)):
        raise CatalogError("duplicate command id")
    runnable = {c.argv for c in cmds if not c.host}
    if runnable != ALLOWED_RUNNABLE:
        extra = runnable - ALLOWED_RUNNABLE
        missing = ALLOWED_RUNNABLE - runnable
        raise CatalogError(f"allowlist mismatch extra={extra!r} missing={missing!r}")
    return cmds


def runnable_commands(cmds: Sequence[Command]) -> list[Command]:
    return [c for c in cmds if not c.host]


def validate_host(value: str) -> str:
    if len(value) > 255 or not value:
        raise CatalogError("DEPLOY_HOST missing or too long")
    if value.startswith("-") or HOST_BAD.search(value):
        raise CatalogError("DEPLOY_HOST is not a valid host")
    if not (HOST_NAME_RE.fullmatch(value) or HOST_IPV4_RE.fullmatch(value)):
        raise CatalogError("DEPLOY_HOST is not a valid host")
    return value


def resolve_deploy_host(
    environ: Mapping[str, str],
    local_env_path: Path | None = None,
) -> str:
    env_path = local_env_path if local_env_path is not None else LOCAL_ENV_PATH
    raw = environ.get("DEPLOY_HOST")
    if raw:
        if raw != raw.strip():
            raise CatalogError("DEPLOY_HOST is not a valid host")
        return validate_host(raw)
    if env_path.is_symlink():
        raise CatalogError("deploy/local.env must not be a symlink")
    if not env_path.is_file():
        raise CatalogError(
            "DEPLOY_HOST is unset; export it or add a DEPLOY_HOST= line in deploy/local.env"
        )
    found: str | None = None
    for line in env_path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if stripped.startswith("DEPLOY_HOST="):
            found = stripped[len("DEPLOY_HOST=") :]
    if found is None or found == "":
        raise CatalogError(
            "DEPLOY_HOST is unset; export it or add a DEPLOY_HOST= line in deploy/local.env"
        )
    if (found.startswith('"') and found.endswith('"') and len(found) >= 2) or (
        found.startswith("'") and found.endswith("'") and len(found) >= 2
    ):
        found = found[1:-1]
    return validate_host(found)


def split_howto(text: str) -> tuple[str, str, str]:
    head = HOW_TO_HEAD.search(text)
    if not head:
        raise CatalogError("README.md is missing ## How to run")
    start = head.start()
    rest = text[head.end() :]
    nxt = NEXT_H2.search(rest)
    end = head.end() + nxt.start() if nxt else len(text)
    return text[:start], text[start:end], text[end:]


def _expected_inner(lines: Sequence[str]) -> str:
    return "```bash\n" + "\n".join(lines) + "\n```\n"


def fence_lines_from_inner(inner: str) -> list[str]:
    text = inner[:-1] if inner.endswith("\n") else inner
    lines = text.splitlines()
    if len(lines) < 2 or lines[0].strip() != "```bash" or lines[-1].strip() != "```":
        raise CatalogError("marker body is not a bash fence")
    return lines[1:-1]


def unmarked_howto_fences(section: str) -> list[str]:
    stripped = MARKER_PAIR.sub("", section)
    return [body.strip() for body in BASH_FENCE.findall(stripped)]


def apply_markers(section: str, cmds: Sequence[Command]) -> str:
    by_block: dict[str, list[Command]] = {}
    for cmd in cmds:
        by_block.setdefault(cmd.block, []).append(cmd)
    found = list(MARKER_PAIR.finditer(section))
    names = [m.group(1) for m in found]
    if len(names) != len(set(names)):
        raise CatalogError("duplicate README markers")
    if set(names) != set(by_block):
        raise CatalogError(
            f"marker/catalog block mismatch have={sorted(names)} want={sorted(by_block)}"
        )
    for match in found:
        inner = match.group(2)
        if "<!-- commands:" in inner or "<!-- /commands:" in inner:
            raise CatalogError("nested README markers")
    out = section
    for match in reversed(found):
        block = match.group(1)
        inner = _expected_inner([c.fence_line() for c in by_block[block]])
        out = out[: match.start(2)] + inner + out[match.end(2) :]
    unmarked = unmarked_howto_fences(out)
    if len(unmarked) != 1 or "./run.sh" not in unmarked[0]:
        raise CatalogError("How to run must have exactly one unmarked TUI launch fence")
    return out


def check_readme(
    cmds: Sequence[Command],
    *,
    readme_path: Path | None = None,
) -> None:
    path = readme_path if readme_path is not None else README_PATH
    prefix, section, suffix = split_howto(path.read_text(encoding="utf-8"))
    del prefix, suffix
    expected = apply_markers(section, cmds)
    by_block: dict[str, list[Command]] = {}
    for cmd in cmds:
        by_block.setdefault(cmd.block, []).append(cmd)
    for match in MARKER_PAIR.finditer(section):
        block = match.group(1)
        got = fence_lines_from_inner(match.group(2))
        want = [c.fence_line() for c in by_block[block]]
        if got != want:
            raise CatalogError(f"stale fence for {block}: {got!r} != {want!r}")
    # Re-run apply_markers on the live section so unmarked-fence rules hold.
    if apply_markers(section, cmds) != expected:
        raise CatalogError("README How to run markers are inconsistent")
    unmarked = unmarked_howto_fences(section)
    if len(unmarked) != 1 or "./run.sh" not in unmarked[0]:
        raise CatalogError("How to run must have exactly one unmarked TUI launch fence")


def _assert_readme_write_path(path: Path, root: Path) -> None:
    expected = (root / "README.md").resolve()
    if path.is_symlink() or path.resolve() != expected:
        raise CatalogError("refusing to write a README.md symlink or path outside root")


def sync_readme(
    cmds: Sequence[Command],
    *,
    readme_path: Path | None = None,
    root: Path | None = None,
) -> None:
    path = readme_path if readme_path is not None else README_PATH
    repo = root if root is not None else ROOT
    _assert_readme_write_path(path, repo)
    text = path.read_text(encoding="utf-8")
    prefix, section, suffix = split_howto(text)
    new_section = apply_markers(section, cmds)
    new_text = prefix + new_section + suffix
    fd, tmp = tempfile.mkstemp(prefix=".README.md.sync.", dir=str(repo), text=True)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(new_text)
        os.replace(tmp, path)
    except Exception:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


DESTRUCTIVE_IDS = frozenset(
    {
        "ingest",
        "refresh",
        "deploy",
        "deploy-ingest",
        "ssh-forward",
        "integration",
        "ingest-pdf",
        "refresh-pdf",
        "l1",
    }
)


@dataclass
class PickerState:
    index: int
    digits: str = ""


def move_index(index: int, delta: int, n: int) -> int:
    if n <= 0:
        return 0
    return (index + delta) % n


def parse_jump(digits: str, n: int) -> int | None:
    if not digits:
        return None
    try:
        one = int(digits)
    except ValueError:
        return None
    if 1 <= one <= n:
        return one - 1
    return None


def handle_key(state: PickerState, token: str, n: int) -> tuple[PickerState, Action]:
    if token == "quit":
        return state, "quit"
    if token == "esc":
        if state.digits:
            return PickerState(state.index, ""), "redraw"
        return state, "redraw"
    if token in {"up", "down"}:
        delta = -1 if token == "up" else 1
        return PickerState(move_index(state.index, delta, n), ""), "redraw"
    if token == "enter":
        if state.digits:
            jump = parse_jump(state.digits, n)
            if jump is None:
                return PickerState(state.index, ""), "redraw"
            return PickerState(jump, ""), "run"
        return state, "run"
    if token.startswith("digit:"):
        return PickerState(state.index, state.digits + token.split(":", 1)[1]), "redraw"
    return state, "redraw"


def read_key(
    *,
    read1: Callable[[], str] | None = None,
    wait: Callable[[float], bool] | None = None,
) -> str:
    # Use os.read on the tty fd. sys.stdin.read(1) is TextIOWrapper-buffered:
    # after ESC is consumed, "[A" can sit in that buffer while select() waits
    # on an empty fd, so arrows were decoded as Esc (j/k still worked).
    fd = sys.stdin.fileno() if read1 is None else -1

    def get() -> str:
        if read1 is not None:
            return read1()
        chunk = os.read(fd, 1)
        return chunk.decode("latin-1") if chunk else ""

    def ready(timeout: float) -> bool:
        if wait is not None:
            return wait(timeout)
        import select

        readable, _, _ = select.select([fd], [], [], timeout)
        return bool(readable)

    ch = get()
    if ch == "":
        return "quit"
    if ch in {"\r", "\n"}:
        return "enter"
    if ch in {"q", "Q"}:
        return "quit"
    if ch == "j":
        return "down"
    if ch == "k":
        return "up"
    if ch.isdigit():
        return f"digit:{ch}"
    if ch != "\x1b":
        return "ignore"
    extra: list[str] = []
    for _ in range(3):
        if not ready(0.1):
            break
        nxt = get()
        if not nxt:
            break
        extra.append(nxt)
        rest = "".join(extra)
        if rest in {"[A", "OA"}:
            return "up"
        if rest in {"[B", "OB"}:
            return "down"
        if len(rest) >= 2 and rest[0] in {"[", "O"} and rest[-1].isalpha():
            return "esc"
    return "esc"


def confirm_prompt_text(cmd: Command) -> str:
    line = shlex.join(cmd.argv)
    if cmd.needs_deploy_host:
        return f"{cmd.title}: {line} (host from DEPLOY_HOST)"
    return f"{cmd.title}: {line}"


def detail_text(cmd: Command) -> str:
    return shlex.join(cmd.argv)


def _command_flags(cmd: Command) -> str:
    flags: list[str] = []
    if cmd.tty:
        flags.append("TTY (replaces TUI)")
    if cmd.confirm:
        flags.append("CONFIRM")
    return " ".join(flags)


def _visible_window(index: int, n: int, height: int) -> tuple[int, int]:
    budget = max(1, height - 16)
    if n <= budget:
        return 0, n
    start = max(0, min(index - budget // 2, n - budget))
    return start, start + budget


def _picker_renderable(
    runnable: Sequence[Command],
    state: PickerState,
    *,
    height: int,
) -> Any:
    from rich.console import Group
    from rich.markup import escape
    from rich.panel import Panel
    from rich.table import Table
    from rich.text import Text

    n = len(runnable)
    start, end = _visible_window(state.index, n, height)
    table = Table(title="BCRA Mini-RAG local-dev commands", show_lines=False)
    table.add_column("#", style="bold")
    table.add_column("Group")
    table.add_column("Title")
    table.add_column("Flags")
    for i in range(start, end):
        cmd = runnable[i]
        marker = ">" if i == state.index else " "
        style = "reverse" if i == state.index else None
        table.add_row(
            f"{marker}{i + 1}",
            escape(cmd.group),
            escape(cmd.title),
            _command_flags(cmd),
            style=style,
        )
    detail = detail_text(runnable[state.index])
    jump = f"  jump:{state.digits}" if state.digits else ""
    footer = f"↑↓ select  Enter run  1-{n} jump  q quit{jump}"
    return Group(
        table,
        Panel(Text(detail), title="Selected command"),
        Text(footer),
    )


def _raw_pick(
    runnable: Sequence[Command],
    state: PickerState,
    console: Any,
) -> tuple[PickerState, Action]:
    import termios
    import tty

    from rich.live import Live

    fd = sys.stdin.fileno()
    old = termios.tcgetattr(fd)
    try:
        tty.setcbreak(fd)
        layout = _picker_renderable(
            runnable,
            state,
            height=console.size.height,
        )
        with Live(layout, console=console, screen=False, auto_refresh=False) as live:
            while True:
                live.update(
                    _picker_renderable(
                        runnable,
                        state,
                        height=console.size.height,
                    ),
                    refresh=True,
                )
                token = read_key()
                state, action = handle_key(state, token, len(runnable))
                if action in {"run", "quit"}:
                    return state, action
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old)


def run_command(
    cmd: Command,
    *,
    environ: Mapping[str, str] | None = None,
    root: Path | None = None,
    local_env_path: Path | None = None,
    confirm_fn: Callable[[str], bool] | None = None,
    execvpe_fn: Callable[[str, Sequence[str], Mapping[str, str]], Any] | None = None,
    run_fn: Callable[..., Any] | None = None,
    chdir_fn: Callable[[Path], None] | None = None,
) -> int:
    repo = root if root is not None else ROOT
    env = dict(os.environ if environ is None else environ)
    if cmd.host or cmd.argv[0] == "sudo":
        raise CatalogError("refusing to execute a dump-host command")
    argv = list(cmd.argv)
    if cmd.needs_deploy_host:
        host = resolve_deploy_host(env, local_env_path)
        argv = [*argv, "--", host]
    if cmd.confirm:
        ask = confirm_fn or (_default_confirm)
        if not ask(confirm_prompt_text(cmd)):
            return 0
    if cmd.tty:
        (chdir_fn or os.chdir)(repo)
        (execvpe_fn or os.execvpe)(argv[0], argv, env)
        raise CatalogError("execvpe returned")
    completed = (run_fn or subprocess.run)(
        argv, cwd=str(repo), env=env, shell=False, check=False
    )
    return int(completed.returncode)


def _default_confirm(line: str) -> bool:
    from rich.prompt import Confirm

    return bool(Confirm.ask(f"Run {line}?", default=False))


def pick_and_run(
    cmds: Sequence[Command],
    *,
    prompt_fn: Callable[[str], str] | None = None,
    confirm_fn: Callable[[str], bool] | None = None,
    run_fn: Callable[..., Any] | None = None,
    execvpe_fn: Callable[[str, Sequence[str], Mapping[str, str]], Any] | None = None,
    environ: Mapping[str, str] | None = None,
    root: Path | None = None,
    local_env_path: Path | None = None,
) -> int:
    from rich.console import Console
    from rich.prompt import Prompt

    console = Console()
    runnable = runnable_commands(cmds)
    if not runnable:
        console.print("No runnable commands.")
        return 1
    state = PickerState(0)
    use_raw = prompt_fn is None and sys.stdin.isatty() and sys.stdout.isatty()
    while True:
        cmd: Command | None = None
        if use_raw:
            try:
                state, action = _raw_pick(
                    runnable,
                    state,
                    console,
                )
            except (OSError, ImportError):
                use_raw = False
                continue
            except KeyboardInterrupt:
                return 130
            if action == "quit":
                return 0
            cmd = runnable[state.index]
        else:
            console.print(
                _picker_renderable(
                    runnable,
                    state,
                    height=max(console.size.height, 24),
                )
            )
            if prompt_fn is not None:
                raw = prompt_fn("Number (q to quit)")
            else:
                raw = Prompt.ask("Number (q to quit)", default="q")
            choice = raw.strip().lower()
            if choice in {"", "q"}:
                return 0
            if not choice.isdigit():
                console.print("Enter a number, or q to quit.")
                continue
            jump = parse_jump(choice, len(runnable))
            if jump is None:
                console.print("Number out of range.")
                continue
            state = PickerState(jump)
            cmd = runnable[state.index]
        assert cmd is not None
        try:
            code = run_command(
                cmd,
                environ=environ,
                root=root,
                local_env_path=local_env_path,
                confirm_fn=confirm_fn,
                execvpe_fn=execvpe_fn,
                run_fn=run_fn,
            )
        except CatalogError as exc:
            console.print(str(exc))
            continue
        console.print(f"exit {code}")
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Local-dev command TUI (not for the dump host).")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--sync", action="store_true", help="rewrite README How to run fences")
    group.add_argument("--check", action="store_true", help="exit 1 if README fences are stale")
    args = parser.parse_args(list(argv) if argv is not None else None)
    try:
        cmds = load_catalog()
        if args.check:
            check_readme(cmds)
            return 0
        if args.sync:
            sync_readme(cmds)
            return 0
        return pick_and_run(cmds)
    except CatalogError as exc:
        print(str(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
