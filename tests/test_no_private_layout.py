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
