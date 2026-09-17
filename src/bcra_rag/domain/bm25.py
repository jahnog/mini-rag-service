"""Small in-package BM25 index and reciprocal-rank fusion (no dependency)."""

from __future__ import annotations

import math
from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass, field

from bcra_rag.domain.text import tokenize


@dataclass
class Bm25Index:
    k1: float = 1.5
    b: float = 0.75
    ids: list[str] = field(default_factory=list)
    doc_len: list[int] = field(default_factory=list)
    avg_len: float = 0.0
    postings: dict[str, list[tuple[int, int]]] = field(default_factory=dict)

    @classmethod
    def build(cls, docs: Sequence[tuple[str, str]]) -> Bm25Index:
        index = cls()
        for position, (chunk_id, text) in enumerate(docs):
            tokens = tokenize(text)
            index.ids.append(chunk_id)
            index.doc_len.append(len(tokens))
            for term, count in Counter(tokens).items():
                index.postings.setdefault(term, []).append((position, count))
        index.avg_len = (sum(index.doc_len) / len(index.doc_len)) if index.doc_len else 0.0
        return index

    def search(self, query: str, n: int) -> list[tuple[str, float]]:
        terms = tokenize(query)
        if not terms or not self.ids:
            return []
        total = len(self.ids)
        scores: dict[int, float] = {}
        for term in set(terms):
            posting = self.postings.get(term)
            if not posting:
                continue
            idf = math.log((total - len(posting) + 0.5) / (len(posting) + 0.5) + 1.0)
            for position, count in posting:
                length = self.doc_len[position]
                norm = self.k1 * (1 - self.b + self.b * length / (self.avg_len or 1.0))
                scores[position] = scores.get(position, 0.0) + idf * (
                    count * (self.k1 + 1) / (count + norm)
                )
        ranked = sorted(scores.items(), key=lambda item: (-item[1], item[0]))
        return [(self.ids[position], score) for position, score in ranked[:n]]


def rrf(rankings: Sequence[Sequence[str]], *, k: int = 60) -> list[tuple[str, float]]:
    fused: dict[str, float] = {}
    order: list[str] = []
    for ranking in rankings:
        for rank, item in enumerate(ranking, start=1):
            if item not in fused:
                order.append(item)
            fused[item] = fused.get(item, 0.0) + 1.0 / (k + rank)
    first_seen = {item: position for position, item in enumerate(order)}
    return sorted(fused.items(), key=lambda pair: (-pair[1], first_seen[pair[0]]))
