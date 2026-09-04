from __future__ import annotations

import json
from pathlib import Path

from bcra_rag.adapters.index_fake import FakeIndex
from bcra_rag.use_cases.run_l1 import (
    L1_SCHEMA_KEYS,
    _citation_exact,
    _hit_at_k,
    load_gold,
    run_l1,
)

ROOT = Path(__file__).resolve().parents[1]
GOLD = ROOT / "evals" / "gold.jsonl"

REQUIRED_BUCKETS = {
    "definicion",
    "obligacion",
    "procedimiento",
    "silencio",
    "cross-ref",
    "superseded",
    "post-to",
    "english",
}


def test_empty_gold_is_not_automatic_hit() -> None:
    assert _hit_at_k([], ["A3500"], 5) == 0.0
    assert _hit_at_k([], [], 5) == 1.0
    assert _citation_exact(["A3500"], ["A3500", "texto_ordenado"]) == 0.0
    assert _citation_exact(["A3500"], ["A3500"]) == 1.0


def test_gold_parses_and_buckets() -> None:
    rows = load_gold(GOLD)
    assert 30 <= len(rows) <= 50
    assert len(rows) == 30
    buckets = {str(row.get("bucket")) for row in rows}
    assert REQUIRED_BUCKETS <= buckets
    a9999 = next(row for row in rows if "9999" in str(row["question"]))
    assert a9999["finding"] == "silencio"
    assert a9999["gold_ids"] == []
    english = [row for row in rows if row.get("bucket") == "english"]
    assert english
    assert any(row.get("gold_puntos") for row in english)
    patch = [row for row in rows if row.get("bucket") == "post-to"]
    assert any("3500" in json.dumps(row) and "8359" in json.dumps(row) for row in patch)
    for row in rows:
        assert "id" in row and "question" in row
        assert "gold_ids" in row and "gold_puntos" in row
        assert "finding" in row and "answerable" in row


def test_run_l1_dry_run_schema(tmp_path: Path) -> None:
    out = tmp_path / "l1.json"
    payload = run_l1(
        gold_path=GOLD,
        output_path=out,
        index=FakeIndex(),
        unpublished=True,
    )
    assert out.is_file()
    data = json.loads(out.read_text(encoding="utf-8"))
    for key in L1_SCHEMA_KEYS:
        assert key in data
    assert data["headline_metric"] == "citation_id_exact"
    assert data["unpublished"] is True
    assert data["sample"] is True
    assert "b_documents" in data["chunking"]
    assert "ragas" in data
    assert payload["n"] == 30


def test_operator_script_does_not_boot_gradio() -> None:
    text = (ROOT / "evals" / "run_l1.py").read_text(encoding="utf-8")
    assert "build_app" not in text
    assert "ChromaIndex" in text
    assert "dump_health" in text


def test_shipped_l1_fixture_is_sample() -> None:
    data = json.loads((ROOT / "evals" / "l1.json").read_text(encoding="utf-8"))
    assert data.get("unpublished") or data.get("sample")
    assert data["headline_metric"] == "citation_id_exact"
