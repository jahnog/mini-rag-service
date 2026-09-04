from __future__ import annotations

import httpx
import pytest
import respx

from bcra_rag.adapters.catalog_bcra import BcraCatalog
from bcra_rag.domain.urls import BUSCADOR_URL
from bcra_rag.settings import Settings

A13 = {
    "tipo": "A",
    "numero": "13",
    "titulo": "CAMEX-1",
    "fecha": "1981-03-02",
    "circular": "CAMEX",
    "link": "https://www.bcra.gob.ar/archivos/Pdfs/comytexord/A0013.pdf",
}
A8464 = {
    "tipo": "A",
    "numero": "8464",
    "titulo": "Exterior y Cambios",
    "fecha": "2026-08-06",
    "circular": "CAMEX",
    "link": "https://www.bcra.gob.ar/archivos/Pdfs/comytexord/A8464.pdf",
}


@pytest.fixture
def settings(tmp_path) -> Settings:
    return Settings(data_dir=tmp_path)


@pytest.mark.asyncio
@respx.mock
async def test_catalog_collapses_duplicates_and_keeps_founding_and_newest(
    settings: Settings,
) -> None:
    respx.post(BUSCADOR_URL).mock(
        side_effect=[
            httpx.Response(200, json={"data": [A8464, {**A8464, "titulo": "dup"}, A13]}),
            httpx.Response(200, json={"data": []}),
        ]
    )
    catalog = BcraCatalog(settings)
    docs = await catalog.list_camex_a()
    ids = [d.comm_id for d in docs]
    assert ids == ["A8464", "A13"]
    assert docs[0].title == "Exterior y Cambios"


@pytest.mark.asyncio
@respx.mock
async def test_catalog_never_requests_non_bcra_host(settings: Settings) -> None:
    route = respx.post(BUSCADOR_URL).mock(
        side_effect=[
            httpx.Response(
                200,
                json={
                    "data": [
                        {
                            **A13,
                            "link": "https://www.banxico.org.mx/evil.pdf",
                        },
                        A8464,
                    ]
                },
            ),
            httpx.Response(200, json={"data": []}),
        ]
    )
    catalog = BcraCatalog(settings)
    docs = await catalog.list_camex_a()
    assert [d.comm_id for d in docs] == ["A8464"]
    assert route.called
    for call in route.calls:
        assert "bcra.gob.ar" in str(call.request.url)
        assert "banxico" not in str(call.request.url)


@pytest.mark.asyncio
@respx.mock
async def test_catalog_does_not_fetch_untagged_1990s_ids(settings: Settings) -> None:
    hole = {
        "tipo": "A",
        "numero": "250",
        "titulo": "untagged 1990s A",
        "fecha": "1993-01-01",
        "circular": "",
        "link": "https://www.bcra.gob.ar/archivos/Pdfs/comytexord/A0250.pdf",
    }
    respx.post(BUSCADOR_URL).mock(
        side_effect=[
            httpx.Response(200, json={"data": [A8464, hole, A13]}),
            httpx.Response(200, json={"data": []}),
        ]
    )
    docs = await BcraCatalog(settings).list_camex_a()
    assert [d.comm_id for d in docs] == ["A8464", "A13"]
    assert "A250" not in {d.comm_id for d in docs}


@pytest.mark.asyncio
@respx.mock
async def test_catalog_pagination_newest_first(settings: Settings) -> None:
    respx.post(BUSCADOR_URL).mock(
        side_effect=[
            httpx.Response(200, json={"data": [A8464]}),
            httpx.Response(200, json={"data": [A13]}),
            httpx.Response(200, json={"data": []}),
        ]
    )
    docs = await BcraCatalog(settings).list_camex_a()
    assert [d.comm_id for d in docs] == ["A8464", "A13"]


LIVE_A8464 = {
    "fecha_emision": "2026-08-06",
    "tipo": "A",
    "numero_formateado": 8464,
    "titulo": "Ref.: Circular CAMEX 1-1064 Exterior y Cambios. Adecuaciones.",
    "link_url": None,
    "pdf_path": "/archivos/Pdfs/comytexord/A8464.pdf",
}
LIVE_A13 = {
    "fecha_emision": "1981-03-02",
    "tipo": "A",
    "numero_formateado": 13,
    "titulo": "Ref.: Circular CAMEX 1-1 CAMEX-1",
    "link_url": None,
    "pdf_path": "/archivos/Pdfs/comytexord/A0013.pdf",
}


def _live_page(registros: list[dict], page: int, total_pages: int) -> dict:
    return {
        "success": True,
        "data": {
            "registros": registros,
            "pagination": {
                "page": page,
                "totalPages": total_pages,
                "totalRecords": 2,
                "pageSize": 30,
            },
        },
    }


@pytest.mark.asyncio
@respx.mock
async def test_catalog_reads_nested_registros_and_paginaabsoluta(
    settings: Settings,
) -> None:
    route = respx.post(BUSCADOR_URL).mock(
        side_effect=[
            httpx.Response(200, json=_live_page([LIVE_A8464], 1, 2)),
            httpx.Response(200, json=_live_page([LIVE_A13], 2, 2)),
        ]
    )
    docs = await BcraCatalog(settings).list_camex_a()
    assert [d.comm_id for d in docs] == ["A8464", "A13"]
    assert docs[0].url.endswith("/A8464.pdf")
    assert docs[1].fecha_emision is not None
    assert docs[1].fecha_emision.isoformat() == "1981-03-02"
    assert route.call_count == 2
    bodies = [call.request.content.decode() for call in route.calls]
    assert "paginaabsoluta=1" in bodies[0]
    assert "paginaabsoluta=2" in bodies[1]
    assert "tamanopagina=100" in bodies[0]
