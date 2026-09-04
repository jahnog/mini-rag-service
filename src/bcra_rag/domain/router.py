from __future__ import annotations

import re
from dataclasses import dataclass, field

from bcra_rag.domain.aliases import expand_aliases
from bcra_rag.domain.back_matter import drop_back_matter
from bcra_rag.domain.manifest import Manifest
from bcra_rag.domain.models import Chunk
from bcra_rag.domain.urls import TO_DOC_ID, comm_number, normalize_comm_id
from bcra_rag.ports.index import IndexPort

NAMED_A_RE = re.compile(
    r"(?:comunicaci[oó]n\s+)?(?:com\.?\s*)?\"?A\"?[\s-]*(\d{3,5})\b",
    re.IGNORECASE,
)
LOOKUP_RE = re.compile(
    r"qu[ée]\s+dice|comunicaci[oó]n\s+\"?A|com\.?\s*\"?A",
    re.IGNORECASE,
)
VS_RE = re.compile(r"\bvs\.?\b", re.IGNORECASE)
REGLA_VIGENTE_RE = re.compile(r"regla\s+vigente", re.IGNORECASE)
PUNTO_RE = re.compile(r"\bpunto\s+(\d+(?:\.\d+)*)", re.IGNORECASE)
XREF_RE = re.compile(
    r"(?:v[eé]ase|ver|seg[uú]n)\s+(?:la\s+)?(?:com(?:unicaci[oó]n)?\.?\s*)\"?A\"?[\s-]*(\d{3,5})",
    re.IGNORECASE,
)
VIGENTE_PATTERNS = (
    re.compile(r"\bhoy\b", re.IGNORECASE),
    re.compile(r"\bvigente\b", re.IGNORECASE),
    re.compile(r"\bpuedo\b", re.IGNORECASE),
    re.compile(r"\bqu[ée]\s+exige\b", re.IGNORECASE),
    re.compile(r"\bliquidar\b", re.IGNORECASE),
    re.compile(r"\btoday\b", re.IGNORECASE),
    re.compile(r"\bcurrent\b", re.IGNORECASE),
    re.compile(r"\bliquidate\b", re.IGNORECASE),
)


@dataclass
class RouteResult:
    query: str
    hits: list[Chunk] = field(default_factory=list)
    named_id: str | None = None
    silencio: bool = False
    silencio_reason: str | None = None
    search_count: int = 0
    fetch_count: int = 0


class Router:
    def __init__(
        self,
        index: IndexPort,
        manifest: Manifest,
        *,
        max_search: int = 2,
        max_fetch: int = 2,
    ) -> None:
        self._index = index
        self._manifest = manifest
        self._max_search = max_search
        self._max_fetch = max_fetch

    def route(self, question: str, *, k: int, to_as_of: str | None) -> RouteResult:
        expanded = expand_aliases(question)
        named = exclusive_named_id(question)
        if named:
            result = self._named_fetch(named, question, k)
        elif _has_vigente_intent(expanded):
            result = self._vigente(expanded, k, to_as_of)
        else:
            result = self._similar(expanded, k)
        if result.silencio:
            return result
        result.hits = drop_back_matter(result.hits, expanded)
        result = self._xref_hop(result, question)
        return result

    def _named_fetch(self, comm_id: str, question: str, k: int) -> RouteResult:
        if comm_id not in self._manifest.documents:
            return RouteResult(
                query=question,
                named_id=comm_id,
                silencio=True,
                silencio_reason="missing_document",
            )
        punto = _punto_in(question)
        text = self._index.get_section(comm_id, punto)
        chunk = _chunk_from_section(comm_id, text, self._manifest)
        return RouteResult(
            query=question,
            hits=[chunk] if text.strip() else [],
            named_id=comm_id,
            fetch_count=1,
            silencio=not bool(text.strip()),
            silencio_reason="empty_extract" if not text.strip() else None,
        )

    def _vigente(self, query: str, k: int, to_as_of: str | None) -> RouteResult:
        hits: list[Chunk] = []
        search_count = 0
        if search_count < self._max_search:
            hits.extend(
                self._index.search(
                    query, k=k, filters={"doc_kind": "texto_ordenado"}
                )
            )
            search_count += 1
        extra: list[Chunk] = []
        post_filters = _post_to_filters(self._manifest, to_as_of)
        if search_count < self._max_search:
            extra = self._index.search(query, k=k, filters=post_filters)
            search_count += 1
        merged = _merge_vigente(hits, extra, k)
        return RouteResult(query=query, hits=merged, search_count=search_count)

    def _similar(self, query: str, k: int) -> RouteResult:
        hits = self._index.search(query, k=k)
        return RouteResult(query=query, hits=hits, search_count=1)

    def _xref_hop(self, result: RouteResult, question: str) -> RouteResult:
        if result.fetch_count >= self._max_fetch:
            return result
        joined = " ".join(chunk.text for chunk in result.hits)
        match = XREF_RE.search(joined)
        if not match:
            return result
        target = normalize_comm_id(match.group(1))
        if target in {result.named_id, *(
            str(chunk.metadata.get("doc_id") or "") for chunk in result.hits
        )}:
            return result
        if target in self._manifest.documents:
            if result.fetch_count >= self._max_fetch:
                return result
            text = self._index.get_section(target)
            result.fetch_count += 1
            result.hits.append(_chunk_from_section(target, text, self._manifest))
            return result
        if _depends_on_missing_xref(question, result.hits, target):
            result.silencio = True
            result.silencio_reason = "missing_xref"
            result.hits = []
        return result


def named_ids(question: str) -> list[str]:
    found: list[str] = []
    for match in NAMED_A_RE.finditer(question):
        comm_id = normalize_comm_id(match.group(1))
        if comm_id not in found:
            found.append(comm_id)
    return found


def exclusive_named_id(question: str) -> str | None:
    ids = named_ids(question)
    if not ids:
        return None
    lookup = bool(LOOKUP_RE.search(question))
    vigente = _has_vigente_intent(question)
    comparison = (
        bool(VS_RE.search(question))
        or len(ids) > 1
        or bool(REGLA_VIGENTE_RE.search(question))
    )
    if lookup:
        return ids[0]
    if vigente and comparison:
        return None
    if not vigente:
        return ids[0]
    return None


def _first_named_id(question: str) -> str | None:
    ids = named_ids(question)
    return ids[0] if ids else None


def _punto_in(question: str) -> str | None:
    match = PUNTO_RE.search(question)
    return match.group(1) if match else None


def _has_vigente_intent(text: str) -> bool:
    return any(pattern.search(text) for pattern in VIGENTE_PATTERNS)


def _post_to_filters(manifest: Manifest, to_as_of: str | None) -> dict[str, object]:
    filters: dict[str, object] = {"doc_kind": "comunicacion"}
    if not to_as_of:
        return filters
    entry = manifest.documents.get(to_as_of) or {}
    fecha = entry.get("fecha")
    if fecha:
        filters["fecha"] = {"$gt": str(fecha)}
    else:
        filters["numero"] = {"$gt": to_as_of}
    return filters


def _chunk_from_section(doc_id: str, text: str, manifest: Manifest) -> Chunk:
    entry = manifest.documents.get(doc_id) or {}
    kind = str(entry.get("kind") or ("texto_ordenado" if doc_id == TO_DOC_ID else "comunicacion"))
    return Chunk(
        chunk_id=f"{doc_id}:section",
        text=text,
        metadata={
            "doc_id": doc_id,
            "doc_kind": kind,
            "numero": doc_id,
            "fecha": entry.get("fecha") or "",
            "score": 1.0,
        },
    )


def _merge_vigente(to_hits: list[Chunk], extra: list[Chunk], k: int) -> list[Chunk]:
    seen: set[str] = set()
    to_unique: list[Chunk] = []
    extra_unique: list[Chunk] = []
    for chunk in to_hits:
        if chunk.chunk_id in seen:
            continue
        seen.add(chunk.chunk_id)
        to_unique.append(chunk)
    for chunk in extra:
        if chunk.chunk_id in seen:
            continue
        seen.add(chunk.chunk_id)
        extra_unique.append(chunk)
    if not extra_unique:
        return to_unique[:k]
    post_slots = min(len(extra_unique), max(1, k // 2))
    to_slots = max(0, k - post_slots)
    chosen = to_unique[:to_slots]
    if len(chosen) < to_slots:
        post_slots = min(len(extra_unique), k - len(chosen))
    chosen.extend(extra_unique[:post_slots])
    return chosen[:k]


def _depends_on_missing_xref(question: str, hits: list[Chunk], target: str) -> bool:
    named = _first_named_id(question)
    if named == target:
        return True
    bodies = [re.sub(XREF_RE, "", chunk.text).strip() for chunk in hits]
    remaining = [body for body in bodies if len(body) > 40]
    return not remaining


def comm_sort_key(doc_id: str) -> int:
    try:
        return comm_number(doc_id)
    except ValueError:
        return -1
