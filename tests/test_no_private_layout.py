from __future__ import annotations

import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FORBIDDEN = (
    "content" + "labstudy",
    "chita" + "-ts",
    "/home/" + "redirect",
    "redirect" + "@",
    "User=" + "redirect",
    "sudo -u " + "redirect",
    "ssd-" + "480",
    "/home/" + "javier",
    "Proyectos/" + "Portafolio",
    "Tail" + "scale",
    "tail" + "scale",
)


def test_tracked_files_have_no_private_layout() -> None:
    listed = subprocess.check_output(
        ["git", "ls-files", "-z", "--cached", "--others", "--exclude-standard"],
        cwd=ROOT,
        text=True,
    )
    files = [ROOT / p for p in listed.split("\0") if p]
    hits: list[str] = []
    for path in files:
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        rel = path.relative_to(ROOT).as_posix()
        for needle in FORBIDDEN:
            if needle in text:
                hits.append(f"{rel}: {needle}")
    assert hits == []


def test_gitignore_ignores_dump_and_operator_overlays() -> None:
    text = (ROOT / ".gitignore").read_text(encoding="utf-8")
    assert "\ndata/\n" in text
    ignored = subprocess.check_output(
        [
            "git",
            "check-ignore",
            "-v",
            "data/logs/chat.log",
            "data/phoenix/x",
            "scripts/publish-data.local",
        ],
        cwd=ROOT,
        text=True,
    )
    assert "data/logs/chat.log" in ignored
    assert "data/phoenix/x" in ignored
    assert "scripts/publish-data.local" in ignored
    tracked = subprocess.check_output(
        ["git", "ls-files", "evals/l1.json"],
        cwd=ROOT,
        text=True,
    )
    assert tracked.strip() == "evals/l1.json"
