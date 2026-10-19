"""Simplicity gate: source files stay short. The allowlist may only shrink."""

from __future__ import annotations

from pathlib import Path

SRC = Path(__file__).resolve().parents[1] / "src"
MAX_LINES = 400

# Existing offenders mapped to their current ceiling. Lower or delete an entry
# when the file shrinks; never add one.
CEILING = {
    "bcra_rag/adapters/llm_openai.py": 503,
    "bcra_rag/ui/config.py": 506,
    "bcra_rag/ui/gradio_app.py": 675,
}


def _lines(path: Path) -> int:
    return len(path.read_text(encoding="utf-8").splitlines())


def test_source_files_stay_within_limit() -> None:
    too_long = []
    for path in sorted(SRC.rglob("*.py")):
        key = path.relative_to(SRC).as_posix()
        limit = CEILING.get(key, MAX_LINES)
        if _lines(path) > limit:
            too_long.append(f"{key}: {_lines(path)} > {limit}")
    assert not too_long, "\n".join(too_long)


def test_allowlist_has_no_stale_entries() -> None:
    stale = []
    for key, ceiling in CEILING.items():
        path = SRC / key
        if not path.exists() or _lines(path) <= MAX_LINES:
            stale.append(f"{key}: remove from CEILING")
        elif _lines(path) < ceiling:
            stale.append(f"{key}: lower ceiling to {_lines(path)}")
    assert not stale, "\n".join(stale)
