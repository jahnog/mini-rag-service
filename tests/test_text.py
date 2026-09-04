from bcra_rag.domain.text import decode_text, normalize_extract


def test_hyphen_join_and_header_strip() -> None:
    raw = (
        "B.C.R.A. EXTERIOR Y CAMBIOS Sección 1\n"
        "la regula-\n"
        "ción cambiaria\n"
    )
    assert normalize_extract(raw) == "la regulación cambiaria"


def test_decode_utf8() -> None:
    assert decode_text("ñandú".encode()) == "ñandú"


def test_decode_cp1252_fallback() -> None:
    # 0x91 is a cp1252 curly quote; invalid UTF-8
    data = b"\x91texto"
    assert decode_text(data) == "‘texto"


def test_decode_latin1_fallback() -> None:
    data = "café".encode("latin-1")
    assert decode_text(data) == "café"
