from __future__ import annotations

import asyncio

import httpx
import pytest
import respx

from bcra_rag.adapters.http_fetch import NonPdfError, PoliteFetcher
from bcra_rag.settings import Settings

PDF = b"%PDF-1.4\n1 0 obj\nendobj\n"
HTML = b"<!doctype html><html>nope</html>"
URL = "https://www.bcra.gob.ar/archivos/Pdfs/comytexord/A0013.pdf"


@pytest.fixture
def settings(tmp_path) -> Settings:
    return Settings(
        data_dir=tmp_path,
        download_concurrency=2,
        download_delay_s=0.0,
        user_agent="test-agent",
    )


@pytest.mark.asyncio
@respx.mock
async def test_non_pdf_body_is_not_stored(settings: Settings) -> None:
    respx.get(URL).mock(
        return_value=httpx.Response(
            200, content=HTML, headers={"content-type": "text/html"}
        )
    )
    fetcher = PoliteFetcher(settings)
    with pytest.raises(NonPdfError):
        await fetcher.get_pdf(URL)


@pytest.mark.asyncio
@respx.mock
async def test_pdf_is_returned_and_sends_user_agent(settings: Settings) -> None:
    route = respx.get(URL).mock(
        return_value=httpx.Response(
            200, content=PDF, headers={"content-type": "application/pdf"}
        )
    )
    body = await PoliteFetcher(settings).get_pdf(URL)
    assert body.startswith(b"%PDF")
    assert route.calls[0].request.headers["user-agent"] == "test-agent"


@pytest.mark.asyncio
@respx.mock
async def test_concurrency_stays_within_settings_bound(settings: Settings) -> None:
    gate = asyncio.Event()
    in_flight = 0
    max_seen = 0

    async def handler(request: httpx.Request) -> httpx.Response:
        nonlocal in_flight, max_seen
        in_flight += 1
        max_seen = max(max_seen, in_flight)
        await gate.wait()
        in_flight -= 1
        return httpx.Response(
            200, content=PDF, headers={"content-type": "application/pdf"}
        )

    respx.get(url__startswith="https://www.bcra.gob.ar/").mock(side_effect=handler)
    fetcher = PoliteFetcher(settings)
    urls = [
        f"https://www.bcra.gob.ar/archivos/Pdfs/comytexord/A{i:04d}.pdf"
        for i in range(1, 6)
    ]
    tasks = [asyncio.create_task(fetcher.get_pdf(url)) for url in urls]
    for _ in range(20):
        await asyncio.sleep(0)
        if max_seen >= 2:
            break
    assert max_seen <= 2
    assert max_seen >= 1
    gate.set()
    await asyncio.gather(*tasks)
    assert fetcher.max_in_flight <= 2
