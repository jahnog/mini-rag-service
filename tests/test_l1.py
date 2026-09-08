from __future__ import annotations

from bcra_rag.evals.use_cases.run_l1 import L1_SCHEMA_KEYS, run_l1


def test_l1_lives_in_evals_vertical() -> None:
    assert callable(run_l1)
    assert "retrieval" in L1_SCHEMA_KEYS
    assert "ragas" not in L1_SCHEMA_KEYS
