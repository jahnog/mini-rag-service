from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

DOCKER_ARTIFACTS = (
    "Dockerfile",
    "compose.yaml",
    "compose.yml",
    "docker-compose.yml",
    "docker-compose.yaml",
    ".dockerignore",
)

SKIP_DIRS = {".git", ".venv", "node_modules", "__pycache__", "archive", "data"}
TEXT_SUFFIXES = {
    ".md",
    ".py",
    ".yml",
    ".yaml",
    ".toml",
    ".sh",
    ".service",
    ".cron",
    ".example",
    ".txt",
    ".gitignore",
}


def test_docker_artifact_files_are_absent() -> None:
    for name in DOCKER_ARTIFACTS:
        assert not (ROOT / name).exists(), name


def test_live_tree_has_no_docker_references() -> None:
    hits: list[str] = []
    for path in ROOT.rglob("*"):
        if not path.is_file():
            continue
        if any(part in SKIP_DIRS for part in path.parts):
            continue
        if path.name == "test_no_docker.py":
            continue
        if path.suffix.lower() not in TEXT_SUFFIXES and path.name != ".gitignore":
            continue
        text = path.read_text(encoding="utf-8", errors="replace").lower()
        if "docker" in text:
            hits.append(str(path.relative_to(ROOT)))
    assert hits == []
