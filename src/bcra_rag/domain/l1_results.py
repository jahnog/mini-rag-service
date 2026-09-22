"""Static L1 results document readers shared by the UI and GET /l1.

A missing file is an unpublished sample. The Calidad L1 panel labels it as
such, rather than as an operator run.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

L1_FILENAME = "l1.json"


def load_l1(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {
            "unpublished": True,
            "sample": True,
            "headline_metric": "citation_id_exact",
            "citation_id_exact": None,
            "hit_at_5": None,
            "mrr": None,
        }
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        return {"unpublished": True, "sample": True}
    return raw


def is_sample_l1(data: dict[str, Any]) -> bool:
    return bool(data.get("unpublished") or data.get("sample"))
