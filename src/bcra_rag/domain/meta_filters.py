from __future__ import annotations

from collections.abc import Mapping

from bcra_rag.domain.urls import comm_number


def metadata_matches(metadata: Mapping[str, object], filters: Mapping[str, object] | None) -> bool:
    if not filters:
        return True
    for key, expected in filters.items():
        actual = metadata.get(key)
        if isinstance(expected, dict):
            gt_value = expected.get("$gt")
            if gt_value is None:
                continue
            if key == "numero":
                try:
                    if comm_number(str(actual)) <= comm_number(str(gt_value)):
                        return False
                except ValueError:
                    return False
            elif str(actual or "") <= str(gt_value):
                return False
            continue
        if actual is None or str(actual) != str(expected):
            return False
    return True


def chroma_where(filters: Mapping[str, object] | None) -> dict[str, object] | None:
    """Equality-only where clause. $gt is applied in Python after query."""
    if not filters:
        return None
    clauses: list[dict[str, object]] = []
    for key, expected in filters.items():
        if isinstance(expected, dict):
            continue
        clauses.append({key: expected})
    if not clauses:
        return None
    if len(clauses) == 1:
        return clauses[0]
    return {"$and": clauses}
