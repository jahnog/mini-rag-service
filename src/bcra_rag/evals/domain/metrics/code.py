from __future__ import annotations

import math
import re

from bcra_rag.evals.domain.types import GenerationSample, RetrievalSample, Score

_WS = re.compile(r"\s+")


def _norm(text: str) -> str:
    return _WS.sub(" ", text).strip().lower()


class HitAtK:
    name = "hit_at_5"
    kind = "code"

    def __init__(self, k: int = 5) -> None:
        self._k = k
        self.name = f"hit_at_{k}"

    def score(self, sample: RetrievalSample) -> Score:
        gold = sample.gold.gold_ids
        top = sample.retrieved_ids[: self._k]
        if not gold:
            value = 1.0 if not top else 0.0
        else:
            value = 1.0 if any(item in gold for item in top) else 0.0
        return Score(name=self.name, value=value)


class PrecisionAtK:
    name = "precision_at_5"
    kind = "code"

    def __init__(self, k: int = 5) -> None:
        self._k = k
        self.name = f"precision_at_{k}"

    def score(self, sample: RetrievalSample) -> Score:
        gold = set(sample.gold.gold_ids)
        top = sample.retrieved_ids[: self._k]
        if not gold:
            value = 1.0 if not top else 0.0
        elif not top:
            value = 0.0
        else:
            value = sum(1.0 for item in top if item in gold) / len(top)
        return Score(name=self.name, value=value)


class Mrr:
    name = "mrr"
    kind = "code"

    def score(self, sample: RetrievalSample) -> Score:
        gold = sample.gold.gold_ids
        retrieved = sample.retrieved_ids
        if not gold:
            value = 1.0 if not retrieved else 0.0
        else:
            value = 0.0
            for rank, item in enumerate(retrieved, start=1):
                if item in gold:
                    value = 1.0 / rank
                    break
        return Score(name=self.name, value=value)


class NdcgAtK:
    name = "ndcg_at_5"
    kind = "code"

    def __init__(self, k: int = 5) -> None:
        self._k = k
        self.name = f"ndcg_at_{k}"

    def score(self, sample: RetrievalSample) -> Score:
        gold = sample.gold.gold_ids
        top = sample.retrieved_ids[: self._k]
        if not gold:
            value = 1.0 if not top else 0.0
            return Score(name=self.name, value=value)
        rel = [1.0 if item in gold else 0.0 for item in top]
        dcg = sum(r / math.log2(i + 2) for i, r in enumerate(rel))
        ideal = [1.0] * min(self._k, len(set(gold)))
        idcg = sum(r / math.log2(i + 2) for i, r in enumerate(ideal))
        value = dcg / idcg if idcg else 0.0
        return Score(name=self.name, value=value)


class CitationIdExact:
    name = "citation_id_exact"
    kind = "code"

    def score(self, sample: GenerationSample) -> Score:
        cited = [item.id for item in sample.citations]
        value = 1.0 if set(sample.gold.gold_ids) == set(cited) else 0.0
        return Score(name=self.name, value=value)


class CitationPuntoExact:
    name = "citation_punto_exact"
    kind = "code"

    def score(self, sample: GenerationSample) -> Score | None:
        gold = sample.gold.gold_puntos
        if not gold:
            return None
        cited = [item.punto or "" for item in sample.citations if item.punto]
        value = 1.0 if set(gold) == set(cited) else 0.0
        return Score(name=self.name, value=value)


class CitationSnippetGrounded:
    name = "citation_snippet_grounded"
    kind = "code"

    def score(self, sample: GenerationSample) -> Score:
        context = _norm("\n".join(chunk.text for chunk in sample.context))
        gold_empty = not sample.gold.gold_ids
        if not sample.citations:
            value = 1.0 if gold_empty else 0.0
            return Score(name=self.name, value=value)
        if not context:
            return Score(name=self.name, value=0.0)
        ok = 0
        for citation in sample.citations:
            snippet = _norm(citation.snippet)
            if snippet and snippet in context:
                ok += 1
        value = ok / len(sample.citations)
        return Score(name=self.name, value=value)


class FindingExact:
    name = "finding_exact"
    kind = "code"

    def score(self, sample: GenerationSample) -> Score:
        value = 1.0 if sample.finding.value == sample.gold.finding else 0.0
        return Score(name=self.name, value=value)
