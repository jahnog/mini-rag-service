from bcra_rag.domain.models import Chunk
from bcra_rag.domain.sections import order_chunks, punto_key, section_text


def _c(punto: str | None, text: str, ordinal: int | None = None) -> Chunk:
    meta: dict[str, object] = {"punto": punto or ""}
    if ordinal is not None:
        meta["ordinal"] = ordinal
    return Chunk(f"A1:{text}", text, meta)


def test_punto_key() -> None:
    assert punto_key("3.8.5") == (3, 8, 5)
    assert punto_key(None) == ()
    assert punto_key("3.a") == (3, 10**6)


def test_order_by_ordinal_when_present() -> None:
    chunks = [_c("2", "dos", 1), _c("1", "uno", 0), _c(None, "anexo", 2)]
    assert [c.text for c in order_chunks(chunks)] == ["uno", "dos", "anexo"]


def test_order_by_punto_fallback() -> None:
    chunks = [_c("3", "tres"), _c("1", "uno"), _c("2", "dos")]
    assert [c.text for c in order_chunks(chunks)] == ["uno", "dos", "tres"]


def test_section_punto_with_subpuntos_and_neighbours() -> None:
    chunks = [_c(p, f"p{p}") for p in ("1", "2", "2.1", "2.2", "3", "4")]
    text = section_text(chunks, "2", 10_000)
    assert text.split("\n") == ["p1", "p2", "p2.1", "p2.2", "p3"]


def test_section_missing_punto_uses_whole_ordered_document() -> None:
    chunks = [_c("3", "tres"), _c("1", "uno"), _c("2", "dos")]
    assert section_text(chunks, "9.9.9", 10_000).split("\n") == ["uno", "dos", "tres"]


def test_section_cap() -> None:
    chunks = [_c("1", "x" * 100)]
    assert len(section_text(chunks, None, 40)) == 40
