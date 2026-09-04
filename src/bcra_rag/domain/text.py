from __future__ import annotations

import re

HEADER_RE = re.compile(
    r"^\s*B\.C\.R\.A\.\s+EXTERIOR Y CAMBIOS.*$",
    re.IGNORECASE | re.MULTILINE,
)
HYPHEN_BREAK_RE = re.compile(r"(\w)-\n(\w)")


def decode_text(data: bytes) -> str:
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError:
        try:
            return data.decode("cp1252")
        except UnicodeDecodeError:
            return data.decode("latin-1")


def strip_running_headers(text: str) -> str:
    return HEADER_RE.sub("", text)


def join_hyphenated_lines(text: str) -> str:
    return HYPHEN_BREAK_RE.sub(r"\1\2", text)


def normalize_extract(text: str) -> str:
    cleaned = strip_running_headers(text)
    cleaned = join_hyphenated_lines(cleaned)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    return cleaned.strip()
