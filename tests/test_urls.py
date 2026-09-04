from bcra_rag.domain.urls import (
    absolute_bcra_url,
    constructed_pdf_url,
    is_bcra_host,
    resolve_pdf_url,
)


def test_zero_padded_early_ids() -> None:
    assert constructed_pdf_url("A13").endswith("/A0013.pdf")
    assert constructed_pdf_url("A8464").endswith("/A8464.pdf")


def test_reject_foreign_host_url() -> None:
    assert is_bcra_host("https://www.bcra.gob.ar/x.pdf")
    assert not is_bcra_host("https://www.banxico.org.mx/x.pdf")
    assert (
        resolve_pdf_url("A13", "https://www.banxico.org.mx/x.pdf") is None
    )


def test_relative_pdf_path_is_absolutized() -> None:
    assert absolute_bcra_url("/archivos/Pdfs/comytexord/A8464.pdf").startswith(
        "https://www.bcra.gob.ar/"
    )
    resolved = resolve_pdf_url("A8464", "/archivos/Pdfs/comytexord/A8464.pdf")
    assert resolved == "https://www.bcra.gob.ar/archivos/Pdfs/comytexord/A8464.pdf"
