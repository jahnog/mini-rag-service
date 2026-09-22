from __future__ import annotations

import re
import unicodedata

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
    """Drop the repeated BCRA running header and join a word split by a hyphen.

    This runs before chunking.
    """
    cleaned = strip_running_headers(text)
    cleaned = join_hyphenated_lines(cleaned)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    return cleaned.strip()


SPANISH_STOPWORDS: frozenset[str] = frozenset(
    {
        "el",
        "la",
        "los",
        "las",
        "de",
        "del",
        "y",
        "o",
        "un",
        "una",
        "en",
        "a",
        "que",
        "se",
        "es",
        "por",
        "para",
        "con",
        "the",
        "of",
        "and",
        "qué",
        "como",
        "cómo",
    }
)

_TOKEN_RE = re.compile(r"[a-z0-9]+")
_COMM_RE = re.compile(r"\ba\s?(\d{2,5})\b")


def tokenize(text: str) -> list[str]:
    """Tokens for BM25. Drops Spanish stopwords and tokens shorter than two characters.

    Accents are stripped. "A" plus a number also adds an a#### token.
    """
    lowered = unicodedata.normalize("NFKD", text or "").lower()
    lowered = "".join(ch for ch in lowered if not unicodedata.combining(ch))
    tokens = [
        t for t in _TOKEN_RE.findall(lowered) if len(t) >= 2 and t not in SPANISH_STOPWORDS
    ]
    tokens += [f"a{num}" for num in _COMM_RE.findall(lowered)]
    return tokens
