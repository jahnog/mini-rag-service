from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass

from bcra_rag.domain.models import Chunk

SECCION_RE = re.compile(r"^Secci[oó]n\s+(\d+)\b", re.IGNORECASE)
PUNTO_RE = re.compile(r"^(\d+(?:\.\d+)*)\.?\s+(.*)$")
ANEXO_RE = re.compile(r"^Anexo\b", re.IGNORECASE)


def _digest(text: str) -> str:
    return hashlib.sha1(text.encode("utf-8")).hexdigest()[:12]


def _token_count(text: str) -> int:
    return len(text.split())


def _hard_split(text: str, max_chars: int) -> list[str]:
    if max_chars <= 0:
        return [text] if text else []
    return [text[i : i + max_chars] for i in range(0, len(text), max_chars)] or []


def split_to_max_chars(text: str, max_chars: int) -> list[str]:
    if not text:
        return []
    if max_chars <= 0 or len(text) <= max_chars:
        return [text]
    words = text.split()
    if not words:
        return _hard_split(text, max_chars)
    pieces: list[str] = []
    current: list[str] = []
    current_len = 0
    for word in words:
        extra = len(word) + (1 if current else 0)
        if current and current_len + extra > max_chars:
            pieces.append(" ".join(current))
            current = []
            current_len = 0
        if not current and len(word) > max_chars:
            pieces.extend(_hard_split(word, max_chars))
            continue
        current.append(word)
        current_len += extra if current_len else len(word)
    if current:
        pieces.append(" ".join(current))
    return pieces


class FixedChunker:
    def __init__(
        self, size: int = 256, overlap: int = 64, max_chars: int = 2048
    ) -> None:
        self.size = size
        self.overlap = overlap
        self.max_chars = max_chars

    def chunk(self, doc_id: str, text: str, metadata: dict[str, object]) -> list[Chunk]:
        words = text.split()
        if not words:
            return []
        chunks: list[Chunk] = []
        start = 0
        while start < len(words):
            end = min(start + self.size, len(words))
            piece = " ".join(words[start:end])
            for part in split_to_max_chars(piece, self.max_chars):
                chunks.append(
                    Chunk(
                        chunk_id=f"{doc_id}:{_digest(part)}",
                        text=part,
                        metadata={**metadata, "chunker": "A"},
                    )
                )
            if end == len(words):
                break
            start = max(end - self.overlap, start + 1)
        return chunks


@dataclass
class _Unit:
    heading_path: str
    punto: str | None
    body: str
    doc_part: str


class StructuredChunker:
    def __init__(self, max_chars: int = 2048) -> None:
        self.max_chars = max_chars

    def chunk(self, doc_id: str, text: str, metadata: dict[str, object]) -> list[Chunk]:
        units = _merge_small(_parse_units(text))
        chunks: list[Chunk] = []
        used: set[str] = set()
        for index, unit in enumerate(units):
            body = unit.body.strip()
            if not body:
                continue
            prefix = f"{unit.heading_path}\n" if unit.heading_path else ""
            full = f"{prefix}{body}" if prefix else body
            parts = self._parts_for(prefix, full)
            for part_index, part in enumerate(parts):
                punto = unit.punto or _digest(part)
                chunk_id = f"{doc_id}:{punto}:{_digest(part)}"
                if chunk_id in used:
                    chunk_id = f"{chunk_id}:{index}:{part_index}"
                used.add(chunk_id)
                chunks.append(
                    Chunk(
                        chunk_id=chunk_id,
                        text=part,
                        metadata={
                            **metadata,
                            "chunker": "B",
                            "punto": unit.punto,
                            "doc_part": unit.doc_part,
                        },
                    )
                )
        return chunks

    def _parts_for(self, prefix: str, full: str) -> list[str]:
        if len(full) <= self.max_chars:
            return [full]
        remainder = full[len(prefix) :] if prefix and full.startswith(prefix) else full
        budget = self.max_chars - len(prefix)
        if budget < 1:
            return split_to_max_chars(full, self.max_chars)
        pieces = split_to_max_chars(remainder, budget)
        parts = [(prefix + piece) if prefix else piece for piece in pieces]
        capped: list[str] = []
        for part in parts:
            capped.extend(split_to_max_chars(part, self.max_chars))
        return capped


def _parse_units(text: str) -> list[_Unit]:
    section = ""
    doc_part = "cuerpo"
    current: _Unit | None = None
    units: list[_Unit] = []

    def flush() -> None:
        nonlocal current
        if current is not None and current.body.strip():
            units.append(current)
        current = None

    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            if current is not None:
                current.body += "\n"
            continue
        seccion = SECCION_RE.match(line)
        if seccion:
            flush()
            section = f"Sección {seccion.group(1)}"
            doc_part = "cuerpo"
            current = _Unit(section, None, line + "\n", doc_part)
            continue
        if ANEXO_RE.match(line):
            flush()
            doc_part = "anexo"
            heading = f"{section} > Anexo" if section else "Anexo"
            current = _Unit(heading, None, line + "\n", doc_part)
            continue
        punto = PUNTO_RE.match(line)
        if punto:
            flush()
            number, rest = punto.group(1), punto.group(2)
            heading = f"{section} > {number}" if section else number
            current = _Unit(heading, number, f"{number}. {rest}\n", doc_part)
            continue
        if current is None:
            heading = section or ""
            current = _Unit(heading, None, line + "\n", doc_part)
        else:
            current.body += line + "\n"
    flush()
    return units


def _is_child_punto(parent: str | None, child: str | None) -> bool:
    if not parent or not child:
        return False
    return child.startswith(parent + ".")


def _merge_small(units: list[_Unit], min_tokens: int = 80) -> list[_Unit]:
    merged: list[_Unit] = []
    for unit in units:
        if (
            merged
            and _token_count(unit.body) < min_tokens
            and merged[-1].doc_part == unit.doc_part
            and _is_child_punto(merged[-1].punto, unit.punto)
        ):
            prev = merged[-1]
            merged[-1] = _Unit(
                prev.heading_path,
                prev.punto,
                prev.body.rstrip() + "\n" + unit.body,
                prev.doc_part,
            )
        else:
            merged.append(unit)
    return merged


def choose_chunker(kind: str, text: str) -> str:
    if kind == "texto_ordenado":
        return "B"
    if kind == "event":
        return "A"
    if SECCION_RE.search(text) or PUNTO_RE.search(text):
        return "B"
    return "A"
