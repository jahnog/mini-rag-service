from __future__ import annotations

from datetime import date, datetime
from typing import Any

import httpx

from bcra_rag.domain.models import CatalogDocument
from bcra_rag.domain.urls import BUSCADOR_URL, is_bcra_host, normalize_comm_id, resolve_pdf_url
from bcra_rag.settings import Settings

_DATE_FORMATS = ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%Y/%m/%d")


def _parse_date(raw: object) -> date | None:
    if raw is None:
        return None
    text = str(raw).strip()
    if not text:
        return None
    for fmt in _DATE_FORMATS:
        try:
            return datetime.strptime(text[:10], fmt).date()
        except ValueError:
            continue
    return None


_ROW_KEYS = ("registros", "items", "comunicaciones", "resultados", "rows", "data")


def _as_page_number(value: object) -> int | None:
    if isinstance(value, bool) or not isinstance(value, (int, float, str)):
        return None
    try:
        number = int(value)
    except (TypeError, ValueError):
        return None
    return number if number > 0 else None


def _as_rows(value: object) -> list[dict[str, Any]] | None:
    if not isinstance(value, list):
        return None
    return [row for row in value if isinstance(row, dict)]


def _rows_from_payload(
    payload: object,
) -> tuple[list[dict[str, Any]], dict[str, Any] | None]:
    if isinstance(payload, list):
        return [row for row in payload if isinstance(row, dict)], None
    if not isinstance(payload, dict):
        return [], None
    data = payload.get("data")
    pagination: dict[str, Any] | None = None
    source: dict[str, Any] = payload
    if isinstance(data, dict):
        maybe_pagination = data.get("pagination")
        if isinstance(maybe_pagination, dict):
            pagination = maybe_pagination
        source = data
        nested = _as_rows(data.get("registros"))
        if nested is not None:
            return nested, pagination
    elif isinstance(data, list):
        return [row for row in data if isinstance(row, dict)], None
    for key in _ROW_KEYS:
        rows = _as_rows(source.get(key))
        if rows is not None:
            return rows, pagination
    return [], pagination


def _field(row: dict[str, Any], *names: str) -> str:
    for name in names:
        value = row.get(name)
        if value is not None and str(value).strip():
            return str(value).strip()
    return ""


class BcraCatalog:
    def __init__(
        self,
        settings: Settings,
        *,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self._settings = settings
        self._client = client

    async def list_camex_a(self) -> list[CatalogDocument]:
        owned = self._client is None
        client = self._client or httpx.AsyncClient(
            headers={"User-Agent": self._settings.user_agent},
            timeout=30.0,
            follow_redirects=True,
        )
        try:
            return await self._paginate(client)
        finally:
            if owned:
                await client.aclose()

    async def _paginate(self, client: httpx.AsyncClient) -> list[CatalogDocument]:
        seen: dict[str, CatalogDocument] = {}
        order: list[str] = []
        page = 1
        while True:
            rows, pagination = await self._fetch_page(client, page)
            if not rows:
                break
            added = 0
            for row in rows:
                doc = self._to_document(row)
                if doc is None:
                    continue
                if doc.comm_id in seen:
                    continue
                seen[doc.comm_id] = doc
                order.append(doc.comm_id)
                added += 1
            if added == 0:
                break
            if pagination:
                current = _as_page_number(pagination.get("page"))
                total_pages = _as_page_number(pagination.get("totalPages"))
                if current is not None and total_pages is not None and current >= total_pages:
                    break
            page += 1
            if page > 500:
                break
        return [seen[key] for key in order]

    async def _fetch_page(
        self, client: httpx.AsyncClient, page: int
    ) -> tuple[list[dict[str, Any]], dict[str, Any] | None]:
        if not is_bcra_host(BUSCADOR_URL):
            return [], None
        response = await client.post(
            BUSCADOR_URL,
            data={
                "mode": "tipo-circular",
                "tipo": "A",
                "circular": "CAMEX",
                "paginaabsoluta": str(page),
                "tamanopagina": "100",
                "pagina": str(page),
            },
        )
        response.raise_for_status()
        try:
            payload: object = response.json()
        except ValueError:
            return [], None
        return _rows_from_payload(payload)

    def _to_document(self, row: dict[str, Any]) -> CatalogDocument | None:
        tipo = _field(row, "tipo", "tipoComunicacion").upper() or "A"
        circular = _field(row, "circular", "circularAsociada").upper()
        title = _field(row, "titulo", "title", "referencia", "tema")
        if tipo != "A":
            return None
        if "CAMEX" not in f"{circular} {title}".upper():
            return None
        raw_id = _field(
            row,
            "numero",
            "nro",
            "id",
            "comunicacion",
            "nro_comunicacion",
            "numero_formateado",
        )
        if not raw_id:
            return None
        try:
            comm_id = normalize_comm_id(raw_id)
        except ValueError:
            return None
        catalog_url = _field(
            row, "url", "link", "pdf", "archivo", "href", "pdf_path", "link_url"
        )
        url = resolve_pdf_url(comm_id, catalog_url or None)
        if url is None:
            return None
        return CatalogDocument(
            comm_id=comm_id,
            title=title,
            url=url,
            fecha_emision=_parse_date(_field(row, "fecha", "fecha_emision", "fechaEmision")),
            tipo="A",
            circular="CAMEX",
        )
