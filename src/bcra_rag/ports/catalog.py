from __future__ import annotations

from typing import Protocol

from bcra_rag.domain.models import CatalogDocument


class CatalogPort(Protocol):
    async def list_camex_a(self) -> list[CatalogDocument]: ...
