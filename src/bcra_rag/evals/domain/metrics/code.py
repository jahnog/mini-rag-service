from __future__ import annotations

import math
import re

from bcra_rag.evals.domain.types import GenerationSample, RetrievalSample, Score

_WS = re.compile(r"\s+")


def _norm(text: str) -> str:
    return _WS.sub(" ", text).strip().lower()


class HitAtK:
    """1 if any gold document id is in the top k, else 0.

    A gold row with no ids (a silencio question) scores 1 only when the search
    also returned nothing, and 0 when it returned anything.
    """

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
    """Fraction of the top k ids that are gold ids. Not judged context precision.

    A gold row with no ids scores 1 only when the search returned nothing.
    """

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
    """1 / rank of the first gold id (1, then 1/2, 1/3, …).

    A gold row with no ids scores 1 only when the search returned nothing.
    """

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
    """Ranking quality in [0, 1]. Each gold id counts once, at its first rank.

    An earlier rank counts more: 1 / log2(rank + 1). A gold row with no ids
    scores 1 only when the search returned nothing.
    """

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
        seen: set[str] = set()
        rel: list[float] = []
        for item in top:
            hit = item in gold and item not in seen
            if hit:
                seen.add(item)
            rel.append(1.0 if hit else 0.0)
        # i is zero-based, so log2(i + 2) is log2(rank + 1).
        dcg = sum(r / math.log2(i + 2) for i, r in enumerate(rel))
        ideal = [1.0] * min(self._k, len(set(gold)))
        idcg = sum(r / math.log2(i + 2) for i, r in enumerate(ideal))
        value = dcg / idcg if idcg else 0.0
        return Score(name=self.name, value=value)


class CitationIdExact:
    """1 when the cited document ids equal the gold ids, as sets.

    Order and duplicates do not matter. This is the headline L1 metric. It
    compares cited ids, not retrieved ids.
    """

    name = "citation_id_exact"
    kind = "code"

    def score(self, sample: GenerationSample) -> Score:
        cited = [item.id for item in sample.citations]
        value = 1.0 if set(sample.gold.gold_ids) == set(cited) else 0.0
        return Score(name=self.name, value=value)


class CitationPuntoExact:
    """1 when the cited puntos equal the gold puntos, as sets. No score if gold has none."""

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
    """Fraction of snippets that are a normalized substring of the given context.

    No citations on a gold row with no ids scores 1. Citations with no context
    score 0.
    """

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
    """1 when the final finding label equals gold, after demote_finding."""

    name = "finding_exact"
    kind = "code"

    def score(self, sample: GenerationSample) -> Score:
        value = 1.0 if sample.finding.value == sample.gold.finding else 0.0
        return Score(name=self.name, value=value)
