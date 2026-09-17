from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Protocol

from bcra_rag.schemas import LlmDraft

OnThinking = Callable[[str], Awaitable[None]]


class LlmBadJson(ValueError):
    """The model body is not a usable JSON answer object."""


class LlmPort(Protocol):
    async def complete(
        self,
        prompt: str,
        *,
        on_thinking: OnThinking | None = None,
        thinking: bool | None = None,
    ) -> LlmDraft: ...
