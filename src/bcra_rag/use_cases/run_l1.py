from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path
from typing import Any

import structlog

from bcra_rag.adapters.index_fake import FakeIndex
from bcra_rag.domain.manifest import Manifest
from bcra_rag.domain.models import Chunk
from bcra_rag.domain.router import Router
from bcra_rag.ports.index import IndexPort
from bcra_rag.use_cases.rebuild_ab import rebuild_structured_slice

log = structlog.get_logger(__name__)

L1_SCHEMA_KEYS = (
    "unpublished",
    "sample",
    "headline_metric",
    "citation_id_exact",
    "hit_at_5",
    "mrr",
    "chunking",
    "slices",
    "ragas",
)


def load_gold(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        rows.append(json.loads(line))
    return rows


def _hit_at_k(gold_ids: list[str], retrieved: list[str], k: int) -> float:
    top = retrieved[:k]
    if not gold_ids:
        return 1.0 if not top else 0.0
    return 1.0 if any(item in gold_ids for item in top) else 0.0


def _rr(gold_ids: list[str], retrieved: list[str]) -> float:
    if not gold_ids:
        return 1.0 if not retrieved else 0.0
    for rank, item in enumerate(retrieved, start=1):
        if item in gold_ids:
            return 1.0 / rank
    return 0.0


def _citation_exact(gold_ids: list[str], cited: list[str]) -> float:
    return 1.0 if set(gold_ids) == set(cited) else 0.0


def run_l1(
    *,
    gold_path: Path,
    output_path: Path,
    index: IndexPort | None = None,
    manifest: Manifest | None = None,
    unpublished: bool = True,
) -> dict[str, Any]:
    rows = load_gold(gold_path)
    resolved_index: IndexPort
    if index is None:
        seeded = FakeIndex()
        _seed_demo_index(seeded)
        resolved_index = seeded
        manifest = manifest or _demo_manifest()
    else:
        resolved_index = index
        manifest = manifest or Manifest(path=Path("."), to_as_of="A8307")
    router = Router(resolved_index, manifest)

    hits: list[float] = []
    rrs: list[float] = []
    exacts: list[float] = []
    slices: dict[str, list[float]] = defaultdict(list)
    for row in rows:
        gold_ids = list(row.get("gold_ids") or [])
        result = router.route(str(row["question"]), k=5, to_as_of=manifest.to_as_of)
        retrieved = [str(chunk.metadata.get("doc_id") or "") for chunk in result.hits]
        cited = list(dict.fromkeys(retrieved))
        if result.silencio:
            cited = []
            retrieved = []
        h = _hit_at_k(gold_ids, retrieved, 5)
        r = _rr(gold_ids, retrieved)
        e = _citation_exact(gold_ids, cited)
        hits.append(h)
        rrs.append(r)
        exacts.append(e)
        slices[str(row.get("bucket") or "other")].append(e)

    extracts: dict[str, tuple[str, dict[str, object]]] = {}
    if isinstance(resolved_index, FakeIndex):
        extracts = {
            doc_id: ("\n".join(c.text for c in chunks), {"doc_kind": "texto_ordenado"})
            for doc_id, chunks in resolved_index.docs.items()
            if doc_id == "texto_ordenado"
        }
    b_chunks = rebuild_structured_slice(extracts, strategy="B") if extracts else []
    a_chunks = rebuild_structured_slice(extracts, strategy="A") if extracts else []
    payload = {
        "unpublished": unpublished,
        "sample": unpublished,
        "headline_metric": "citation_id_exact",
        "citation_id_exact": _mean(exacts),
        "hit_at_5": _mean(hits),
        "mrr": _mean(rrs),
        "chunking": {
            "A": len(a_chunks),
            "B": len(b_chunks),
            "b_documents": list(extracts),
        },
        "slices": {key: _mean(vals) for key, vals in sorted(slices.items())},
        "ragas": None,
        "n": len(rows),
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    log.info("l1_run", **payload)
    return payload


def _mean(values: list[float]) -> float:
    return round(sum(values) / len(values), 4) if values else 0.0


def _demo_manifest() -> Manifest:
    return Manifest(
        path=Path("."),
        to_as_of="A8307",
        documents={
            "texto_ordenado": {"kind": "texto_ordenado"},
            "A3500": {"kind": "comunicacion", "fecha": "2002-03-08"},
            "A8307": {"kind": "comunicacion", "fecha": "2025-08-25"},
            "A8359": {"kind": "comunicacion", "fecha": "2025-09-01"},
        },
    )


def _seed_demo_index(index: FakeIndex) -> None:
    index.upsert(
        "texto_ordenado",
        [
            Chunk(
                "texto_ordenado:3.8.5:x",
                "Los residentes deberán liquidar el cobro de exportaciones en el MULC.",
                {
                    "doc_kind": "texto_ordenado",
                    "punto": "3.8.5",
                    "chunker": "B",
                    "numero": "texto_ordenado",
                },
            )
        ],
    )
    index.upsert(
        "A3500",
        [
            Chunk(
                "A3500:1",
                "Tipo de cambio de referencia 2002.",
                {
                    "doc_kind": "comunicacion",
                    "fecha": "2002-03-08",
                    "numero": "A3500",
                    "chunker": "A",
                },
            )
        ],
    )
    index.upsert(
        "A8359",
        [
            Chunk(
                "A8359:1",
                "Adecuación del tipo de cambio de referencia posterior al TO.",
                {
                    "doc_kind": "comunicacion",
                    "fecha": "2025-09-01",
                    "numero": "A8359",
                    "chunker": "A",
                },
            )
        ],
    )
