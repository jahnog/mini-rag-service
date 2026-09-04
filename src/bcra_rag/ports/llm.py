from __future__ import annotations

from typing import Protocol

from bcra_rag.schemas import LlmDraft


class LlmPort(Protocol):
    async def complete(self, prompt: str) -> LlmDraft: ...
