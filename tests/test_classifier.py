from datetime import date

from bcra_rag.domain.classifier import DocKind, classify_title, parse_to_as_of


def test_reprint_pack_is_event() -> None:
    assert (
        classify_title("Actualización del texto ordenado Exterior y Cambios")
        == DocKind.EVENT
    )


def test_reprint_wins_over_adecuacion() -> None:
    title = "Adecuación. Actualización del texto ordenado. Hojas de reemplazo"
    assert classify_title(title) == DocKind.EVENT


def test_adecuacion_is_full_extract() -> None:
    assert classify_title("Exterior y Cambios. Adecuaciones.") == DocKind.FULL


def test_post_to_as_of_stays_full() -> None:
    kind = classify_title("Adecuaciones al régimen.")
    assert kind == DocKind.FULL
    assert date(2026, 8, 6) > date(2025, 8, 25)


def test_to_document_kind() -> None:
    assert classify_title("t-excbio", is_texto_ordenado=True) == DocKind.TEXTO_ORDENADO


def test_parse_to_as_of_from_header() -> None:
    header = (
        "BANCO CENTRAL DE LA REPÚBLICA ARGENTINA\n"
        "TEXTO ORDENADO DE LAS NORMAS SOBRE EXTERIOR Y CAMBIOS\n"
        "Última comunicación incorporada: A 8307 (25/08/2025)\n"
    )
    assert parse_to_as_of(header) == "A8307"
