from __future__ import annotations

import json
from pathlib import Path

import pytest

from bcra_rag.evals.domain.gate import evaluate_gate, load_thresholds

ROOT = Path(__file__).resolve().parents[2]


def test_load_thresholds(tmp_path: Path) -> None:
    path = tmp_path / "gate.toml"
    path.write_text("[thresholds]\nhit_at_5 = 0.8\nmrr = 0.7\n", encoding="utf-8")
    assert load_thresholds(path) == {"hit_at_5": 0.8, "mrr": 0.7}
    bad = tmp_path / "bad.toml"
    bad.write_text("[other]\nx = 1\n", encoding="utf-8")
    with pytest.raises(ValueError):
        load_thresholds(bad)
    bad.write_text("[thresholds]\nx = 'no'\n", encoding="utf-8")
    with pytest.raises(ValueError):
        load_thresholds(bad)


def test_committed_document_passes_default_floors() -> None:
    payload = json.loads((ROOT / "evals" / "l1.json").read_text(encoding="utf-8"))
    floors = load_thresholds(ROOT / "evals" / "gate.toml")
    assert evaluate_gate(payload, floors) == []
    assert evaluate_gate(payload, {"mrr": 0.9}) == ["mrr: 0.7806 < 0.9"]
    assert evaluate_gate(payload, {"nope": 0.1}) == ["nope: missing"]


def test_skipped_suite_fails_unless_allowed() -> None:
    payload = {
        "retrieval": {"skipped": False, "hit_at_5": 0.9},
        "generation": {"skipped": True, "skip_reason": "missing_extra"},
    }
    assert evaluate_gate(payload, {"finding_exact": 0.1}) == [
        "finding_exact: generation skipped (missing_extra)"
    ]
    assert evaluate_gate(payload, {"finding_exact": 0.1}, allow_skipped=True) == []
    assert evaluate_gate(payload, {"hit_at_5": 0.95}) == ["hit_at_5: 0.9 < 0.95"]
