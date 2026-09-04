from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable

import httpx

from bcra_rag.domain.urls import is_bcra_host
from bcra_rag.settings import Settings

SleepFn = Callable[[float], Awaitable[None]]

_PDF_MAGIC = b"%PDF"


class NonPdfError(ValueError):
    pass


class PoliteFetcher:
    def __init__(
        self,
        settings: Settings,
        *,
        client: httpx.AsyncClient | None = None,
        sleep: SleepFn = asyncio.sleep,
    ) -> None:
        self._settings = settings
        self._client = client
        self._sleep = sleep
        self._sem = asyncio.Semaphore(settings.download_concurrency)
        self.in_flight = 0
        self.max_in_flight = 0

    async def get_pdf(self, url: str) -> bytes:
        if not is_bcra_host(url):
            raise NonPdfError(f"refusing non-BCRA host: {url}")
        owned = self._client is None
        client = self._client or httpx.AsyncClient(
            headers={"User-Agent": self._settings.user_agent},
            timeout=60.0,
            follow_redirects=True,
        )
        try:
            async with self._sem:
                self.in_flight += 1
                self.max_in_flight = max(self.max_in_flight, self.in_flight)
                try:
                    return await self._get_pdf(client, url)
                finally:
                    self.in_flight -= 1
                    if self._settings.download_delay_s > 0:
                        await self._sleep(self._settings.download_delay_s)
        finally:
            if owned:
                await client.aclose()

    async def _get_pdf(self, client: httpx.AsyncClient, url: str) -> bytes:
        response = await client.get(url)
        response.raise_for_status()
        body = response.content
        content_type = response.headers.get("content-type", "").lower()
        if not _looks_like_pdf(body[:16], content_type):
            raise NonPdfError(f"not a PDF: {url}")
        return body


def _looks_like_pdf(prefix: bytes, content_type: str) -> bool:
    if prefix.lstrip().startswith(_PDF_MAGIC):
        return True
    if content_type.startswith("application/pdf"):
        return prefix.lstrip().startswith(_PDF_MAGIC)
    return False
