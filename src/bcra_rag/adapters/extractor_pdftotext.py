from __future__ import annotations

import subprocess
import tempfile
from pathlib import Path

from bcra_rag.domain.text import decode_text, normalize_extract


class PdfExtractor:
    def extract_pdf(self, raw_bytes: bytes) -> str:
        text = self._pdftotext(raw_bytes)
        return normalize_extract(text)

    def _pdftotext(self, raw_bytes: bytes) -> str:
        with tempfile.TemporaryDirectory() as tmp:
            pdf_path = Path(tmp) / "doc.pdf"
            pdf_path.write_bytes(raw_bytes)
            try:
                completed = subprocess.run(
                    [
                        "pdftotext",
                        "-layout",
                        "-enc",
                        "UTF-8",
                        str(pdf_path),
                        "-",
                    ],
                    check=False,
                    capture_output=True,
                )
            except FileNotFoundError as exc:
                raise RuntimeError(
                    "pdftotext not found; install poppler-utils"
                ) from exc
            if completed.returncode == 0 and completed.stdout:
                return decode_text(completed.stdout)
            if completed.stdout:
                return decode_text(completed.stdout)
            return ""
