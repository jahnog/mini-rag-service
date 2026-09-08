import tomllib
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "test.yml"


def test_ci_workflow_has_no_live_bcra_or_embeddings() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")
    assert WORKFLOW.is_file()
    assert "bcra.gob.ar" not in text
    assert "OPENAI_API_KEY" not in text
    assert "EMBEDDING_API_KEY" not in text
    assert "LLM_API_KEY" not in text
    assert "poppler" not in text.lower()
    assert "uv run ruff check" in text
    assert "uv run mypy src" in text
    assert "uv run pytest" in text
    assert "--cov=src" in text


def test_coverage_gate_invariants() -> None:
    config = (ROOT / "openspec" / "config.yaml").read_text(encoding="utf-8")
    pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    assert "src coverage MUST be >= 80%" in config
    assert "fix until green" in config
    assert "fail_under = 80" in pyproject


def test_pypi_phoenix_package_is_not_a_dependency() -> None:
    pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    lock = tomllib.loads((ROOT / "uv.lock").read_text(encoding="utf-8"))
    required = pyproject["project"]["dependencies"]
    extras = pyproject["project"]["optional-dependencies"]
    assert not any(_dist_name(item) == "phoenix" for item in required)
    assert not any(
        _dist_name(item) == "phoenix" for pkgs in extras.values() for item in pkgs
    )
    assert "phoenix" not in {pkg["name"] for pkg in lock.get("package", [])}


def test_pypi_phoenix_distribution_is_not_installed() -> None:
    with pytest.raises(PackageNotFoundError):
        version("phoenix")


def _dist_name(requirement: str) -> str:
    for separator in ("[", ">", "<", "=", ";", " "):
        requirement = requirement.split(separator, 1)[0]
    return requirement.strip()
