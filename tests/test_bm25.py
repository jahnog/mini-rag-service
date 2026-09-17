from bcra_rag.domain.bm25 import Bm25Index, rrf
from bcra_rag.domain.text import tokenize


def test_tokenize_keeps_numbers_and_joins_comunicacion_ids() -> None:
    tokens = tokenize("Comunicación A 3500 punto 8.4.1 de la norma")
    assert "a3500" in tokens
    assert "3500" in tokens
    assert "punto" in tokens
    assert "de" not in tokens and "la" not in tokens
    assert "comunicacion" in tokens


def test_bm25_ranks_rare_term_first() -> None:
    index = Bm25Index.build(
        [
            ("c1", "tipo de cambio de referencia promedio ponderado"),
            ("c2", "el sistema SECOEXPO recibe la documentación comercial"),
            ("c3", "liquidación del cobro de exportaciones en el mercado"),
        ]
    )
    ranked = index.search("SECOEXPO", 3)
    assert ranked and ranked[0][0] == "c2"
    assert index.search("zzzz", 3) == []
    assert Bm25Index.build([]).search("algo", 3) == []


def test_rrf_prefers_items_on_both_lists() -> None:
    fused = rrf([["a", "b"], ["b", "c"]])
    assert fused[0][0] == "b"
    assert [item for item, _ in fused] == ["b", "a", "c"]
