from __future__ import annotations

import json
from pathlib import Path

from bcra_rag.evals.domain.types import GoldRow


def load_gold(path: Path) -> list[GoldRow]:
    rows: list[GoldRow] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        raw = json.loads(line)
        reference = raw.get("reference_answer")
        rows.append(
            GoldRow(
                id=str(raw["id"]),
                question=str(raw["question"]),
                gold_ids=list(raw.get("gold_ids") or []),
                gold_puntos=list(raw.get("gold_puntos") or []),
                finding=str(raw.get("finding") or ""),
                answerable=bool(raw.get("answerable")),
                bucket=str(raw.get("bucket") or "other"),
                reference_answer=str(reference) if reference else None,
            )
        )
    return rows
