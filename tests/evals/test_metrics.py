from __future__ import annotations

from bcra_rag.domain.models import Chunk
from bcra_rag.evals.domain.aggregate import collect
from bcra_rag.evals.domain.metrics import (
    CitationIdExact,
    CitationPuntoExact,
    CitationSnippetGrounded,
    FindingExact,
    HitAtK,
    Mrr,
    NdcgAtK,
    PrecisionAtK,
)
from bcra_rag.evals.domain.types import GenerationSample, GoldRow, RetrievalSample, Score
from bcra_rag.schemas import Citation, Finding


def _gold(**kwargs: object) -> GoldRow:
    base = {
        "id": "g",
        "question": "q",
        "gold_ids": ["A3500"],
        "gold_puntos": ["1"],
        "finding": "definicion",
        "answerable": True,
        "bucket": "definicion",
    }
    base.update(kwargs)
    return GoldRow(**base)  # type: ignore[arg-type]


def _chunk(doc_id: str, text: str = "hello") -> Chunk:
    return Chunk(f"{doc_id}:1", text, {"doc_id": doc_id})


def test_empty_gold_is_not_automatic_hit() -> None:
    empty = _gold(gold_ids=[], gold_puntos=[])
    sample = RetrievalSample(gold=empty, hits=[_chunk("A3500")], retrieved_ids=["A3500"])
    assert HitAtK(5).score(sample).value == 0.0
    none = RetrievalSample(gold=empty, hits=[], retrieved_ids=[])
    assert HitAtK(5).score(none).value == 1.0
    assert PrecisionAtK(5).score(sample).value == 0.0
    gen = GenerationSample(
        gold=_gold(),
        context=[],
        context_source="oracle",
        answer="",
        citations=[
            Citation(id="A3500", tipo="A", snippet="x"),
            Citation(id="texto_ordenado", tipo="TO", snippet="y"),
        ],
        finding=Finding.DEFINICION,
    )
    assert CitationIdExact().score(gen).value == 0.0
    exact = GenerationSample(
        gold=_gold(),
        context=[],
        context_source="oracle",
        answer="",
        citations=[Citation(id="A3500", tipo="A", snippet="x")],
        finding=Finding.DEFINICION,
    )
    assert CitationIdExact().score(exact).value == 1.0


def test_mrr_and_precision() -> None:
    gold = _gold()
    sample = RetrievalSample(
        gold=gold,
        hits=[_chunk("A1"), _chunk("A3500")],
        retrieved_ids=["A1", "A3500"],
    )
    assert Mrr().score(sample).value == 0.5
    assert PrecisionAtK(5).score(sample).value == 0.5


def test_citation_punto_skip_and_snippet_grounded() -> None:
    no_puntos = GenerationSample(
        gold=_gold(gold_puntos=[]),
        context=[_chunk("A3500", "tipo de cambio de referencia 2002")],
        context_source="oracle",
        answer="x",
        citations=[Citation(id="A3500", tipo="A", snippet="tipo de cambio de referencia 2002")],
        finding=Finding.DEFINICION,
    )
    assert CitationPuntoExact().score(no_puntos) is None
    assert CitationSnippetGrounded().score(no_puntos).value == 1.0
    bad = GenerationSample(
        gold=_gold(),
        context=[_chunk("A3500", "tipo de cambio")],
        context_source="oracle",
        answer="x",
        citations=[Citation(id="A3500", tipo="A", snippet="not in context")],
        finding=Finding.DEFINICION,
    )
    assert CitationSnippetGrounded().score(bad).value == 0.0


def test_silencio_finding_exact() -> None:
    gold = _gold(id="g13", gold_ids=[], gold_puntos=[], finding="silencio", answerable=False)
    sample = GenerationSample(
        gold=gold,
        context=[],
        context_source="oracle",
        answer="silencio",
        citations=[],
        finding=Finding.SILENCIO,
    )
    assert FindingExact().score(sample).value == 1.0
    assert CitationIdExact().score(sample).value == 1.0


def test_collect_drops_none_scores() -> None:
    grouped = collect([Score(name="hit_at_5", value=1.0), None])
    assert grouped["hit_at_5"] == [1.0]




def test_ndcg_counts_each_gold_id_once() -> None:
    gold = _gold(gold_ids=["texto_ordenado"], gold_puntos=[])
    ids = ["texto_ordenado", "texto_ordenado", "A8359", "texto_ordenado", "A3500"]
    sample = RetrievalSample(gold=gold, hits=[_chunk(i) for i in ids], retrieved_ids=ids)
    assert NdcgAtK(5).score(sample).value == 1.0


def test_ndcg_first_hit_rank_and_bound() -> None:
    import math

    gold = _gold(gold_ids=["A3500"], gold_puntos=[])
    ids = ["A8359", "A3500", "A3500", "A3500", "A3500"]
    sample = RetrievalSample(gold=gold, hits=[_chunk(i) for i in ids], retrieved_ids=ids)
    value = NdcgAtK(5).score(sample).value
    assert abs(value - 1 / math.log2(3)) < 1e-9
    assert 0.0 <= value <= 1.0
