from __future__ import annotations

from urllib.parse import urlparse

BUSCADOR_URL = "https://www.bcra.gob.ar/api/endpoints/buscador-comunicaciones.php"
TO_PDF_URL = "https://www.bcra.gob.ar/Pdfs/Texord/t-excbio.pdf"
TO_DOC_ID = "texto_ordenado"
PDF_BASE = "https://www.bcra.gob.ar/archivos/Pdfs/comytexord"
BCRA_ORIGIN = "https://www.bcra.gob.ar"


def is_bcra_host(url: str) -> bool:
    host = (urlparse(url).hostname or "").lower()
    return host == "bcra.gob.ar" or host.endswith(".bcra.gob.ar")


def absolute_bcra_url(url: str) -> str:
    text = url.strip()
    if text.startswith("/"):
        return BCRA_ORIGIN + text
    return text


def normalize_comm_id(raw: str) -> str:
    digits = "".join(ch for ch in raw if ch.isdigit())
    if not digits:
        raise ValueError(f"not a Comunicación A id: {raw!r}")
    return f"A{int(digits)}"


def comm_number(comm_id: str) -> int:
    return int(normalize_comm_id(comm_id)[1:])


def constructed_pdf_url(comm_id: str) -> str:
    n = comm_number(comm_id)
    padded = f"{n:04d}"
    return f"{PDF_BASE}/A{padded}.pdf"


def resolve_pdf_url(comm_id: str, catalog_url: str | None) -> str | None:
    if catalog_url:
        absolute = absolute_bcra_url(catalog_url)
        if is_bcra_host(absolute):
            return absolute
        return None
    return constructed_pdf_url(comm_id)
