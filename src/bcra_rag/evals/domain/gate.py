"""Threshold gate over a published L1 results document."""

from __future__ import annotations

import tomllib
from collections.abc import Mapping
from pathlib import Path
from typing import Any

_BLOCKS = ("retrieval", "generation")
_OWNER: dict[str, str] = {
    "hit_at_5": "retrieval",
    "precision_at_5": "retrieval",
    "mrr": "retrieval",
    "ndcg_at_5": "retrieval",
    "context_precision": "retrieval",
    "context_recall": "retrieval",
    "citation_id_exact": "generation",
    "citation_punto_exact": "generation",
    "citation_snippet_grounded": "generation",
    "finding_exact": "generation",
    "faithfulness": "generation",
    "answer_relevancy": "generation",
}


def load_thresholds(path: Path) -> dict[str, float]:
    raw = tomllib.loads(path.read_text(encoding="utf-8"))
    table = raw.get("thresholds")
    if not isinstance(table, dict) or not table:
        raise ValueError(f"{path}: missing [thresholds] table")
    floors: dict[str, float] = {}
    for name, value in table.items():
        if isinstance(value, bool) or not isinstance(value, int | float):
            raise ValueError(f"{path}: threshold {name!r} must be a number")
        floors[str(name)] = float(value)
    return floors


def evaluate_gate(
    payload: Mapping[str, Any],
    thresholds: Mapping[str, float],
    *,
    allow_skipped: bool = False,
) -> list[str]:
    failures: list[str] = []
    for name, floor in thresholds.items():
        block_name = _OWNER.get(name) or next(
            (
                candidate
                for candidate in _BLOCKS
                if isinstance(payload.get(candidate), dict) and name in payload[candidate]
            ),
            None,
        )
        block = payload.get(block_name) if block_name else None
        if not isinstance(block, dict):
            failures.append(f"{name}: missing")
            continue
        if block.get("skipped"):
            if not allow_skipped:
                reason = block.get("skip_reason") or "omitido"
                failures.append(f"{name}: {block_name} skipped ({reason})")
            continue
        value = block.get(name)
        if value is None or float(value) < floor:
            failures.append(f"{name}: {value} < {floor}")
    return failures
