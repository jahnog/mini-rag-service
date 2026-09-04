from __future__ import annotations

import json
from typing import Any

import pytest
from pydantic import ValidationError

from bcra_rag.adapters.llm_fake import FakeLlm, UnavailableLlm
from bcra_rag.adapters.llm_openai import LlmAdapter, parse_llm_draft
from bcra_rag.schemas import Finding, LlmDraft
from bcra_rag.settings import Settings


@pytest.mark.asyncio
async def test_fake_llm_returns_structured_draft() -> None:
    llm = FakeLlm(
        LlmDraft(answer="Fuente: A3500", finding=Finding.DEFINICION, citations=[])
    )
    draft = await llm.complete("prompt")
    assert draft.finding is Finding.DEFINICION
    assert "Fuente:" in draft.answer
    assert llm.calls == ["prompt"]


@pytest.mark.asyncio
async def test_unavailable_llm_records_call_and_raises() -> None:
    llm = UnavailableLlm()
    with pytest.raises(RuntimeError, match="LLM_API_KEY"):
        await llm.complete("nope")
    assert llm.calls == ["nope"]


def test_parse_llm_draft_fuente_string_is_texto_ordenado() -> None:
    draft = parse_llm_draft(
        json.dumps(
            {
                "answer": "Fuente: texto_ordenado",
                "finding": "obligacion",
                "citations": "Fuente: texto_ordenado",
            }
        )
    )
    assert draft.finding is Finding.OBLIGACION
    assert len(draft.citations) == 1
    assert draft.citations[0].id == "texto_ordenado"
    assert draft.citations[0].tipo == "TO"


def test_parse_llm_draft_list_of_ids_is_comunicacion_a() -> None:
    draft = parse_llm_draft(
        json.dumps(
            {
                "answer": "Fuente: A8359",
                "finding": "definicion",
                "citations": ["A8359"],
            }
        )
    )
    assert len(draft.citations) == 1
    assert draft.citations[0].id == "A8359"
    assert draft.citations[0].tipo == "A"


def test_parse_llm_draft_object_missing_tipo_is_to() -> None:
    draft = parse_llm_draft(
        json.dumps(
            {
                "answer": "cláusula",
                "finding": "procedimiento",
                "citations": [{"id": "texto_ordenado", "punto": "1.3"}],
            }
        )
    )
    assert draft.citations[0].id == "texto_ordenado"
    assert draft.citations[0].tipo == "TO"
    assert draft.citations[0].punto == "1.3"


def test_parse_llm_draft_unusable_citations_are_empty() -> None:
    draft = parse_llm_draft(
        json.dumps(
            {
                "answer": "sin fuente",
                "finding": "silencio",
                "citations": "see above",
            }
        )
    )
    assert draft.citations == []


def test_parse_llm_draft_invalid_finding_is_silencio() -> None:
    draft = parse_llm_draft(
        json.dumps({"answer": "ok", "finding": "not-a-finding", "citations": []})
    )
    assert draft.finding is Finding.SILENCIO


def test_parse_llm_draft_missing_answer_fails() -> None:
    with pytest.raises(ValidationError):
        parse_llm_draft(json.dumps({"finding": "silencio", "citations": []}))


class _Message:
    def __init__(self, content: str) -> None:
        self.content = content


class _Choice:
    def __init__(self, content: str) -> None:
        self.message = _Message(content)


class _Response:
    def __init__(self, content: str) -> None:
        self.choices = [_Choice(content)]


class _Completions:
    def __init__(self, content: str) -> None:
        self.content = content
        self.kwargs: list[dict[str, Any]] = []

    async def create(self, **kwargs: Any) -> _Response:
        self.kwargs.append(kwargs)
        return _Response(self.content)


class _Chat:
    def __init__(self, content: str) -> None:
        self.completions = _Completions(content)


class StubOpenAI:
    def __init__(self, content: str) -> None:
        self.chat = _Chat(content)


@pytest.mark.asyncio
async def test_adapter_complete_coerces_string_citations() -> None:
    payload = json.dumps(
        {
            "answer": "last_refresh=x; to_as_of=y. Fuente: texto_ordenado",
            "finding": "obligacion",
            "citations": "Fuente: texto_ordenado",
        }
    )
    client = StubOpenAI(payload)
    llm = LlmAdapter(Settings(llm_api_key="sk-test"), client=client)
    draft = await llm.complete("pregunta")
    assert draft.citations[0].id == "texto_ordenado"
    assert draft.citations[0].tipo == "TO"
    assert client.chat.completions.kwargs[0]["response_format"] == {
        "type": "json_object"
    }
    system = client.chat.completions.kwargs[0]["messages"][0]["content"]
    assert "array of objects" in system
    assert "Fuente:" in system
    assert llm.calls == ["pregunta"]
