from __future__ import annotations

from bcra_rag.schemas import Finding, LlmDraft


class FakeLlm:
    def __init__(self, draft: LlmDraft | None = None) -> None:
        self.calls: list[str] = []
        self.draft = draft or LlmDraft(
            answer="silencio",
            finding=Finding.SILENCIO,
            citations=[],
        )

    async def complete(self, prompt: str) -> LlmDraft:
        self.calls.append(prompt)
        return self.draft


class UnavailableLlm:
    def __init__(self) -> None:
        self.calls: list[str] = []

    async def complete(self, prompt: str) -> LlmDraft:
        self.calls.append(prompt)
        raise RuntimeError("LLM_API_KEY is not set")
