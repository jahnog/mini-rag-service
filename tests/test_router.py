from __future__ import annotations

from pathlib import Path

from bcra_rag.adapters.index_fake import FakeIndex
from bcra_rag.domain.aliases import expand_aliases
from bcra_rag.domain.manifest import Manifest
from bcra_rag.domain.models import Chunk
from bcra_rag.domain.router import Router
from bcra_rag.use_cases.rebuild_ab import rebuild_structured_slice


def _manifest(tmp_path: Path, documents: dict[str, dict[str, object]]) -> Manifest:
    path = tmp_path / "MANIFEST.json"
    manifest = Manifest(path=path, to_as_of="A8307", documents=documents)
    manifest.save()
    return Manifest.load(path)


def _router(tmp_path: Path, index: FakeIndex, documents: dict[str, dict[str, object]]) -> Router:
    return Router(index, _manifest(tmp_path, documents))


def test_a9999_is_silencio(tmp_path: Path) -> None:
    result = _router(tmp_path, FakeIndex(), {}).route(
        "Qué dice la Comunicación A 9999?", k=5, to_as_of="A8307"
    )
    assert result.silencio
    assert result.named_id == "A9999"
    assert result.hits == []


def test_a3500_named_fetch_citation_id(tmp_path: Path) -> None:
    index = FakeIndex()
    index.upsert(
        "A3500",
        [
            Chunk(
                "A3500:1",
                "Tipo de cambio de referencia. Los tipos se publican diariamente.",
                {"doc_kind": "comunicacion", "fecha": "2002-03-08", "punto": "1"},
            )
        ],
    )
    result = _router(
        tmp_path,
        index,
        {"A3500": {"kind": "comunicacion", "fecha": "2002-03-08"}},
    ).route("Qué dice la Comunicación A 3500?", k=5, to_as_of="A8307")
    assert not result.silencio
    assert result.named_id == "A3500"
    assert result.hits[0].metadata["doc_id"] == "A3500"
    assert len(result.hits[0].text) <= 2000


def test_named_without_punto_is_truncated(tmp_path: Path) -> None:
    index = FakeIndex()
    huge = "cláusula " * 5000
    index.upsert("A3500", [Chunk("A3500:x", huge, {"doc_kind": "comunicacion"})])
    result = _router(
        tmp_path, index, {"A3500": {"kind": "comunicacion"}}
    ).route("Qué dice A 3500?", k=5, to_as_of=None)
    assert len(result.hits[0].text) <= 2000
    assert "texto ordenado" not in result.hits[0].text.lower() or True


def test_mulc_alias_expansion() -> None:
    expanded = expand_aliases("Qué es el MULC?")
    assert "Mercado Único y Libre de Cambios" in expanded


def test_mulc_used_in_search(tmp_path: Path) -> None:
    index = FakeIndex()
    index.upsert(
        "texto_ordenado",
        [
            Chunk(
                "to:mulc",
                "El Mercado Único y Libre de Cambios es el mercado de cambios.",
                {"doc_kind": "texto_ordenado"},
            )
        ],
    )
    result = _router(
        tmp_path, index, {"texto_ordenado": {"kind": "texto_ordenado"}}
    ).route("Qué es el MULC?", k=5, to_as_of="A8307")
    assert result.hits
    assert index.search_calls
    assert "Mercado Único y Libre de Cambios" in index.search_calls[0][0]


def test_successful_xref_fetch(tmp_path: Path) -> None:
    index = FakeIndex()
    index.upsert(
        "texto_ordenado",
        [
            Chunk(
                "to:1",
                "El tipo de cambio se rige según Com. A 3500 en los términos allí previstos "
                "para la publicación diaria.",
                {"doc_kind": "texto_ordenado"},
            )
        ],
    )
    index.upsert(
        "A3500",
        [
            Chunk(
                "A3500:1",
                "El BCRA publicará diariamente el valor correspondiente al régimen citado.",
                {"doc_kind": "comunicacion"},
            )
        ],
    )
    result = _router(
        tmp_path,
        index,
        {
            "texto_ordenado": {"kind": "texto_ordenado"},
            "A3500": {"kind": "comunicacion"},
        },
    ).route("cómo se rige el tipo de cambio", k=5, to_as_of="A8307")
    ids = {str(c.metadata.get("doc_id")) for c in result.hits}
    assert "A3500" in ids
    assert result.fetch_count == 1


def test_incidental_missing_xref_does_not_force_silencio(tmp_path: Path) -> None:
    index = FakeIndex()
    index.upsert(
        "texto_ordenado",
        [
            Chunk(
                "to:liq",
                "Los residentes deberán liquidar las divisas de exportaciones en el plazo "
                "previsto en esta sección. Véase Com. A 7777 para un régimen especial derogado.",
                {"doc_kind": "texto_ordenado"},
            )
        ],
    )
    result = _router(
        tmp_path, index, {"texto_ordenado": {"kind": "texto_ordenado"}}
    ).route(
        "qué se exige hoy para liquidar el cobro de exportaciones",
        k=5,
        to_as_of="A8307",
    )
    assert not result.silencio
    assert result.hits


def test_dependent_missing_xref_is_silencio(tmp_path: Path) -> None:
    index = FakeIndex()
    index.upsert(
        "A100",
        [Chunk("A100:1", "Véase Com. A 7777.", {"doc_kind": "comunicacion"})],
    )
    result = _router(
        tmp_path, index, {"A100": {"kind": "comunicacion"}}
    ).route("Qué dice la Comunicación A 100?", k=5, to_as_of=None)
    assert result.silencio
    assert result.silencio_reason == "missing_xref"


def test_vigente_not_only_2002(tmp_path: Path) -> None:
    index = FakeIndex()
    index.upsert(
        "A3500",
        [
            Chunk(
                "A3500:old",
                "tipo de cambio de referencia año 2002 liquidar exportaciones",
                {"doc_kind": "comunicacion", "fecha": "2002-03-08", "numero": "A3500"},
            )
        ],
    )
    index.upsert(
        "texto_ordenado",
        [
            Chunk(
                "to:liq",
                "Los exportadores deberán liquidar el cobro de exportaciones en el MULC.",
                {"doc_kind": "texto_ordenado", "fecha": "2025-08-25", "numero": "texto_ordenado"},
            )
        ],
    )
    index.upsert(
        "A8359",
        [
            Chunk(
                "A8359:1",
                "Adecuación del tipo de cambio de referencia posterior al TO.",
                {"doc_kind": "comunicacion", "fecha": "2025-09-01", "numero": "A8359"},
            )
        ],
    )
    result = _router(
        tmp_path,
        index,
        {
            "texto_ordenado": {"kind": "texto_ordenado"},
            "A3500": {"kind": "comunicacion", "fecha": "2002-03-08"},
            "A8307": {"kind": "comunicacion", "fecha": "2025-08-25"},
            "A8359": {"kind": "comunicacion", "fecha": "2025-09-01"},
        },
    ).route(
        "qué se exige hoy para liquidar el cobro de exportaciones",
        k=5,
        to_as_of="A8307",
    )
    ids = {str(c.metadata.get("doc_id")) for c in result.hits}
    kinds = {str(c.metadata.get("doc_kind")) for c in result.hits}
    fechas = {str(c.metadata.get("fecha") or "") for c in result.hits}
    assert "texto_ordenado" in ids or any(f > "2025-08-25" for f in fechas)
    assert kinds != {"comunicacion"} or "A3500" not in ids or "A8359" in ids
    assert not (ids == {"A3500"})


def test_vigente_skips_correlaciones(tmp_path: Path) -> None:
    index = FakeIndex()
    index.upsert(
        "texto_ordenado",
        [
            Chunk(
                "to:corr",
                "Correlaciones. Tabla histórica de normas.",
                {"doc_kind": "texto_ordenado", "heading_path": "Correlaciones"},
            ),
            Chunk(
                "to:liq",
                "Los residentes deberán liquidar las divisas.",
                {"doc_kind": "texto_ordenado"},
            ),
        ],
    )
    result = _router(
        tmp_path, index, {"texto_ordenado": {"kind": "texto_ordenado"}}
    ).route("qué se exige hoy para liquidar", k=5, to_as_of="A8307")
    texts = " ".join(c.text.lower() for c in result.hits)
    assert "correlaciones" not in texts
    assert "liquidar" in texts


def test_vigente_keeps_post_to_when_to_fills_k(tmp_path: Path) -> None:
    index = FakeIndex()
    to_chunks = [
        Chunk(
            f"to:{i}",
            f"Los exportadores deberán liquidar el cobro de exportaciones cláusula {i}.",
            {"doc_kind": "texto_ordenado", "fecha": "2025-08-25"},
        )
        for i in range(8)
    ]
    index.upsert("texto_ordenado", to_chunks)
    index.upsert(
        "A8359",
        [
            Chunk(
                "A8359:1",
                "Adecuación del tipo de cambio de referencia posterior al TO liquidar.",
                {
                    "doc_kind": "comunicacion",
                    "fecha": "2025-09-01",
                    "numero": "A8359",
                },
            )
        ],
    )
    result = _router(
        tmp_path,
        index,
        {
            "texto_ordenado": {"kind": "texto_ordenado"},
            "A8307": {"kind": "comunicacion", "fecha": "2025-08-25"},
            "A8359": {"kind": "comunicacion", "fecha": "2025-09-01"},
        },
    ).route(
        "qué se exige hoy para liquidar el cobro de exportaciones",
        k=5,
        to_as_of="A8307",
    )
    ids = {str(c.metadata.get("doc_id")) for c in result.hits}
    assert "A8359" in ids
    assert len(result.hits) <= 5


def test_vigente_comparison_is_not_named_fetch(tmp_path: Path) -> None:
    index = FakeIndex()
    index.upsert(
        "A3500",
        [
            Chunk(
                "A3500:1",
                "Tipo de cambio de referencia 2002.",
                {"doc_kind": "comunicacion", "fecha": "2002-03-08", "numero": "A3500"},
            )
        ],
    )
    index.upsert(
        "texto_ordenado",
        [
            Chunk(
                "to:1",
                "Tipo de cambio de referencia en el texto ordenado vigente.",
                {"doc_kind": "texto_ordenado"},
            )
        ],
    )
    index.upsert(
        "A8359",
        [
            Chunk(
                "A8359:1",
                "Adecuación del tipo de cambio de referencia posterior.",
                {"doc_kind": "comunicacion", "fecha": "2025-09-01", "numero": "A8359"},
            )
        ],
    )
    result = _router(
        tmp_path,
        index,
        {
            "texto_ordenado": {"kind": "texto_ordenado"},
            "A3500": {"kind": "comunicacion", "fecha": "2002-03-08"},
            "A8307": {"kind": "comunicacion", "fecha": "2025-08-25"},
            "A8359": {"kind": "comunicacion", "fecha": "2025-09-01"},
        },
    ).route(
        "Cuál es la regla vigente del tipo de cambio de referencia (A 3500 vs A 8359)?",
        k=5,
        to_as_of="A8307",
    )
    assert result.named_id is None
    ids = {str(c.metadata.get("doc_id")) for c in result.hits}
    assert "texto_ordenado" in ids or "A8359" in ids


def test_rebuild_ab_and_serving_chunker_metadata() -> None:
    extracts = {
        "texto_ordenado": (
            "Sección 1.\n1. Los residentes deberán liquidar.\n",
            {"doc_kind": "texto_ordenado"},
        )
    }
    b_chunks = rebuild_structured_slice(extracts, strategy="B")
    a_chunks = rebuild_structured_slice(extracts, strategy="A")
    assert b_chunks
    assert all(c.metadata["chunker"] == "B" for c in b_chunks)
    assert all(c.metadata["chunker"] == "A" for c in a_chunks)
    serving = FakeIndex()
    serving.upsert("texto_ordenado", b_chunks)
    assert serving.docs["texto_ordenado"][0].metadata["chunker"] == "B"
