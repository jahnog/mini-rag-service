from __future__ import annotations

from bcra_rag.evals.domain.types import GenerationSample, RetrievalSample, Score
from bcra_rag.evals.ports.judge import Judge


def _context_text(sample: RetrievalSample | GenerationSample) -> str:
    hits = sample.hits if isinstance(sample, RetrievalSample) else sample.context
    return "\n".join(chunk.text for chunk in hits)


class ContextPrecision:
    name = "context_precision"
    kind = "llm"

    def __init__(self, judge: Judge) -> None:
        self._judge = judge

    def score(self, sample: RetrievalSample) -> Score | None:
        if not sample.hits:
            return None
        values: list[float] = []
        for rank, chunk in enumerate(sample.hits, start=1):
            result = self._judge.classify(
                "context_precision",
                {
                    "question": sample.gold.question,
                    "chunk": chunk.text,
                    "rank": str(rank),
                },
            )
            values.append(result.value)
        n = len(values)
        # RAGAS context precision: mean precision@k at relevant ranks (not code precision_at_5).
        hits = 0.0
        total = 0.0
        for index, value in enumerate(values, start=1):
            if value >= 0.5:
                hits += 1
                total += hits / index
        denom = sum(1 for value in values if value >= 0.5) or n
        scored = total / denom if denom else 0.0
        return Score(name=self.name, value=scored, kind="llm")


class ContextRecall:
    name = "context_recall"
    kind = "llm"

    def __init__(self, judge: Judge) -> None:
        self._judge = judge

    def score(self, sample: RetrievalSample) -> Score | None:
        reference = sample.gold.reference_answer
        if not reference:
            return None
        parts = reference.replace("!", ".").split(".")
        sentences = [part.strip() for part in parts if part.strip()]
        if not sentences:
            return None
        context = _context_text(sample)
        supported = 0
        for sentence in sentences:
            result = self._judge.classify(
                "context_recall",
                {"sentence": sentence, "context": context},
            )
            if result.value >= 0.5:
                supported += 1
        return Score(name=self.name, value=supported / len(sentences), kind="llm")


class Faithfulness:
    name = "faithfulness"
    kind = "llm"

    def __init__(self, judge: Judge) -> None:
        self._judge = judge

    def score(self, sample: GenerationSample) -> Score | None:
        if not sample.gold.answerable or not sample.usable_context:
            return None
        context = _context_text(sample)
        return self._judge.classify(
            "faithfulness",
            {"answer": sample.answer, "context": context},
        )


class AnswerRelevancy:
    name = "answer_relevancy"
    kind = "llm"

    def __init__(self, judge: Judge) -> None:
        self._judge = judge

    def score(self, sample: GenerationSample) -> Score | None:
        if not sample.gold.answerable or not sample.usable_context:
            return None
        return self._judge.classify(
            "answer_relevancy",
            {"question": sample.gold.question, "answer": sample.answer},
        )
