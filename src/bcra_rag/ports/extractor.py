from __future__ import annotations

from typing import Protocol


class ExtractorPort(Protocol):
    def extract_pdf(self, raw_bytes: bytes) -> str: ...
