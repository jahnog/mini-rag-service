from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Any


@dataclass(frozen=True)
class CatalogDocument:
    comm_id: str
    title: str
    url: str
    fecha_emision: date | None = None
    tipo: str = "A"
    circular: str = "CAMEX"


@dataclass(frozen=True)
class Chunk:
    chunk_id: str
    text: str
    metadata: dict[str, Any] = field(default_factory=dict)
