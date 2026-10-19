from __future__ import annotations

import re
from typing import Literal

from bcra_rag.domain.urls import TO_DOC_ID
from bcra_rag.schemas import Citation, Finding, LlmDraft

_CHUNK_ID = re.compile(r"\[(?:chunk_id|documento)=([^\s\]]+)")


class FakeLlm:
    def __init__(
        self,
        draft: LlmDraft | None = None,
        *,
        fail_first: type[Exception] | None = None,
    ) -> None:
        self.calls: list[str] = []
        self.thinking_args: list[bool | None] = []
        self.fail_first = fail_first
        self.draft = draft or LlmDraft(
            answer="silencio",
            finding=Finding.SILENCIO,
            citations=[],
        )

    async def complete(
        self,
        prompt: str,
        *,
        thinking: bool | None = None,
    ) -> LlmDraft:
        self.calls.append(prompt)
        self.thinking_args.append(thinking)
        if self.fail_first is not None:
            failure = self.fail_first
            self.fail_first = None
            raise failure("bad")
        ids = _CHUNK_ID.findall(prompt)
        cited = {item.id for item in self.draft.citations}
        if self.draft.citations and ids and not (cited & set(ids)):
            draft = _draft_for_retrieved(self.draft, ids[0], prompt)
        else:
            draft = self.draft
        return draft


def _draft_for_retrieved(draft: LlmDraft, doc_id: str, prompt: str) -> LlmDraft:
    snippet = ""
    token = f"documento={doc_id}"
    for line in prompt.splitlines():
        if token in line and "] " in line:
            snippet = line.split("] ", 1)[1][:280]
            break
    tipo: Literal["A", "TO"] = "TO" if doc_id == TO_DOC_ID else "A"
    return LlmDraft(
        answer=draft.answer,
        finding=draft.finding,
        citations=[Citation(id=doc_id, tipo=tipo, snippet=snippet)],
        thinking=draft.thinking,
    )


class UnavailableLlm:
    def __init__(self) -> None:
        self.calls: list[str] = []
        self.thinking_args: list[bool | None] = []

    async def complete(
        self,
        prompt: str,
        *,
        thinking: bool | None = None,
    ) -> LlmDraft:
        self.calls.append(prompt)
        self.thinking_args.append(thinking)
        raise RuntimeError("LLM_API_KEY is not set")
