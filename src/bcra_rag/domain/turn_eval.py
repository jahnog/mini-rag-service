from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class TurnScores:
    faithfulness: float | None = None
    answer_relevancy: float | None = None

    def as_dict(self) -> dict[str, float]:
        payload: dict[str, float] = {}
        if self.faithfulness is not None:
            payload["faithfulness"] = self.faithfulness
        if self.answer_relevancy is not None:
            payload["answer_relevancy"] = self.answer_relevancy
        return payload


class TurnEvaluator(Protocol):
    async def score(
        self, *, question: str, answer: str, context: str
    ) -> TurnScores: ...


class NoOpTurnEvaluator:
    async def score(
        self, *, question: str, answer: str, context: str
    ) -> TurnScores:
        del question, answer, context
        return TurnScores()
