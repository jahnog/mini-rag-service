import tomllib
from pathlib import Path

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


def test_chromadb_floor_and_unpatched_advisory_ignores() -> None:
    pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    required = pyproject["project"]["dependencies"]
    assert any(item.startswith("chromadb>=1.5.9") for item in required)
    audit = pyproject["tool"]["uv"]["audit"]["ignore-until-fixed"]
    assert "GHSA-f4j7-r4q5-qw2c" in audit
    assert "GHSA-36p7-vc44-83pf" in audit
    assert "GHSA-2wm9-hf6c-p5cr" in audit
    assert "GHSA-xph7-9rjv-w5fr" in audit
