from __future__ import annotations

from collections.abc import Mapping

from bcra_rag.evals.domain.types import Score


class FakeJudge:
    def __init__(self, scores: Mapping[str, Score] | None = None) -> None:
        self.calls: list[tuple[str, Mapping[str, str]]] = []
        self._scores = dict(scores or {})

    def classify(self, name: str, inputs: Mapping[str, str]) -> Score:
        self.calls.append((name, dict(inputs)))
        if name in self._scores:
            return self._scores[name]
        return Score(name=name, value=1.0, kind="llm", label="yes")
