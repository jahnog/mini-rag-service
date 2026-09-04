from bcra_rag.adapters.extractor_pdftotext import PdfExtractor


def test_extract_normalizes_pdftotext_output(monkeypatch) -> None:
    extractor = PdfExtractor()

    def fake_pdf(_: bytes) -> str:
        return "B.C.R.A. EXTERIOR Y CAMBIOS Sección 2\nnorma-\nción\n"

    monkeypatch.setattr(extractor, "_pdftotext", fake_pdf)
    assert extractor.extract_pdf(b"%PDF") == "normación"
