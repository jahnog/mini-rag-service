from bcra_rag.domain.chunkers import FixedChunker, StructuredChunker, split_to_max_chars

TO_LIKE = """
Sección 1. Mercado de cambios.
1. Los residentes deberán liquidar las divisas.
1.1. El plazo es de cinco días hábiles.
1.1.1. x
2. Queda prohibido operar sin conformidad.
Anexo I. Definiciones.
A. Mercado es el MULC.
"""


def test_structured_chunker_on_to_like_text() -> None:
    chunks = StructuredChunker().chunk("to", TO_LIKE, {"doc_kind": "texto_ordenado"})
    ids = [c.chunk_id for c in chunks]
    assert len(ids) == len(set(ids))
    puntos = {c.metadata.get("punto") for c in chunks}
    assert "1" in puntos or any(c.chunk_id.startswith("to:1:") for c in chunks)
    assert any("1.1" in c.text or (c.metadata.get("punto") or "").startswith("1.1") for c in chunks)
    assert all(c.metadata["chunker"] == "B" for c in chunks)
    assert any("Sección 1" in c.text for c in chunks)
    assert ids


def test_structured_chunker_identical_units_stay_unique() -> None:
    text = "1. Same body text here.\n1. Same body text here.\n"
    chunks = StructuredChunker().chunk("to", text, {})
    ids = [c.chunk_id for c in chunks]
    assert len(chunks) == 2
    assert len(ids) == len(set(ids))


def test_structured_chunker_repeated_puntos_get_unique_ids() -> None:
    text = (
        "Sección 1. Índice.\n"
        "2.1. Cobros de exportaciones de bienes listados en el índice.\n"
        "Sección 2. Cuerpo.\n"
        "2.1. Cobros de exportaciones de bienes con el texto completo de la norma.\n"
    )
    chunks = StructuredChunker().chunk("to", text, {})
    ids = [c.chunk_id for c in chunks]
    assert len(ids) == len(set(ids))
    assert sum(1 for c in chunks if c.metadata.get("punto") == "2.1") >= 2


def test_tiny_punto_is_merged() -> None:
    chunks = StructuredChunker().chunk("to", TO_LIKE, {})
    tiny_alone = [c for c in chunks if c.chunk_id.endswith(":1.1.1")]
    assert tiny_alone == []
    assert any("cinco días" in c.text and "1.1.1" in c.text or "x" in c.text for c in chunks)


def test_fixed_chunker_overlaps() -> None:
    words = " ".join(f"w{i}" for i in range(600))
    chunks = FixedChunker(size=512, overlap=128, max_chars=10_000).chunk("A1", words, {})
    assert len(chunks) == 2
    assert all(c.metadata["chunker"] == "A" for c in chunks)
    assert chunks[0].chunk_id.startswith("A1:")


def test_fixed_chunker_default_256_overlap() -> None:
    words = " ".join(f"w{i}" for i in range(600))
    chunks = FixedChunker().chunk("A1", words, {})
    assert len(chunks) > 2
    assert all(len(c.text) <= 2048 for c in chunks)


def test_fixed_chunker_splits_long_words_to_max_chars() -> None:
    words = " ".join("w" * 20 for _ in range(256))
    chunks = FixedChunker(max_chars=2048).chunk("A1", words, {})
    assert chunks
    assert all(len(c.text) <= 2048 for c in chunks)
    assert any(len(c.text) > 256 for c in chunks)


def test_structured_chunker_splits_oversized_punto() -> None:
    body = "palabra " * 400
    text = f"Sección 1. Mercado.\n1. {body}\n"
    chunks = StructuredChunker(max_chars=2048).chunk("to", text, {})
    puntos = [c for c in chunks if c.metadata.get("punto") == "1"]
    assert len(puntos) > 1
    assert all(len(c.text) <= 2048 for c in puntos)
    ids = [c.chunk_id for c in puntos]
    assert len(ids) == len(set(ids))
    assert all("1" in (c.metadata.get("punto") or "") for c in puntos)


def test_split_to_max_chars_keeps_short_text() -> None:
    assert split_to_max_chars("hola", 10) == ["hola"]
