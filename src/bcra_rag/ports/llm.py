from __future__ import annotations

from typing import Protocol

from bcra_rag.schemas import LlmDraft


class LlmBadJson(ValueError):
    """The model body is not a usable JSON answer object."""


class LlmPort(Protocol):
    async def complete(
        self,
        prompt: str,
        *,
        thinking: bool | None = None,
    ) -> LlmDraft:
        """Send the prompt and return a draft with any completed provider trace."""
        ...
