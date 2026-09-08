from __future__ import annotations

from collections import defaultdict

from bcra_rag.evals.domain.types import Score


def mean(values: list[float]) -> float:
    return round(sum(values) / len(values), 4) if values else 0.0


def percentile(values: list[float], p: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = min(len(ordered) - 1, max(0, round((p / 100) * (len(ordered) - 1))))
    return round(ordered[index], 4)


def collect(scores: list[Score | None]) -> dict[str, list[float]]:
    grouped: dict[str, list[float]] = defaultdict(list)
    for score in scores:
        if score is None:
            continue
        grouped[score.name].append(score.value)
    return grouped
