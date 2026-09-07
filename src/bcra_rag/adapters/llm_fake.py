from __future__ import annotations

import re
from typing import Literal

from bcra_rag.domain.urls import TO_DOC_ID
from bcra_rag.schemas import Citation, Finding, LlmDraft

_CHUNK_ID = re.compile(r"\[chunk_id=([^\s\]]+)")


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
        ids = _CHUNK_ID.findall(prompt)
        cited = {item.id for item in self.draft.citations}
        if self.draft.citations and ids and not (cited & set(ids)):
            return _draft_for_retrieved(self.draft, ids[0], prompt)
        return self.draft


def _draft_for_retrieved(draft: LlmDraft, doc_id: str, prompt: str) -> LlmDraft:
    snippet = ""
    token = f"chunk_id={doc_id}"
    for line in prompt.splitlines():
        if token in line and "] " in line:
            snippet = line.split("] ", 1)[1][:280]
            break
    tipo: Literal["A", "TO"] = "TO" if doc_id == TO_DOC_ID else "A"
    return LlmDraft(
        answer=draft.answer,
        finding=draft.finding,
        citations=[Citation(id=doc_id, tipo=tipo, snippet=snippet)],
    )


class UnavailableLlm:
    def __init__(self) -> None:
        self.calls: list[str] = []

    async def complete(self, prompt: str) -> LlmDraft:
        self.calls.append(prompt)
        raise RuntimeError("LLM_API_KEY is not set")
