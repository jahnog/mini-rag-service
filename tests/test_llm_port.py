from __future__ import annotations

import json
from typing import Any

import pytest
from pydantic import ValidationError

from bcra_rag.adapters.llm_fake import FakeLlm, UnavailableLlm
from bcra_rag.adapters.llm_openai import (
    LlmAdapter,
    parse_llm_draft,
    unwrap_thinking_text,
)
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
    assert draft.thinking == ""
    assert llm.calls == ["prompt"]


@pytest.mark.asyncio
async def test_fake_llm_keeps_thinking_trace() -> None:
    llm = FakeLlm(
        LlmDraft(
            answer="Fuente: A3500",
            finding=Finding.DEFINICION,
            citations=[],
            thinking="voy a citar A3500",
        )
    )
    seen: list[str] = []

    async def on_thinking(text: str) -> None:
        seen.append(text)

    draft = await llm.complete("prompt", on_thinking=on_thinking)
    assert draft.thinking == "voy a citar A3500"
    assert seen == ["voy a citar A3500"]


@pytest.mark.asyncio
async def test_fake_llm_think_chunks_grow_callback() -> None:
    llm = FakeLlm(
        LlmDraft(
            answer="Fuente: A3500",
            finding=Finding.DEFINICION,
            citations=[],
            thinking="voy a citar",
        ),
        think_chunks=["voy ", "voy a citar"],
    )
    seen: list[str] = []

    async def on_thinking(text: str) -> None:
        seen.append(text)

    draft = await llm.complete("prompt", on_thinking=on_thinking)
    assert draft.thinking == "voy a citar"
    assert seen == ["voy ", "voy a citar"]


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


class _Delta:
    def __init__(
        self,
        content: str | None = None,
        *,
        reasoning_content: str | None = None,
        reasoning: str | None = None,
    ) -> None:
        self.content = content
        self.reasoning_content = reasoning_content
        self.reasoning = reasoning


class _StreamChoice:
    def __init__(self, delta: _Delta) -> None:
        self.delta = delta


class _StreamChunk:
    def __init__(self, delta: _Delta) -> None:
        self.choices = [_StreamChoice(delta)]


class _ChunkStream:
    def __init__(self, chunks: list[_StreamChunk]) -> None:
        self._chunks = chunks
        self._index = 0

    def __aiter__(self) -> _ChunkStream:
        return self

    async def __anext__(self) -> _StreamChunk:
        if self._index >= len(self._chunks):
            raise StopAsyncIteration
        chunk = self._chunks[self._index]
        self._index += 1
        return chunk


def _delta_chunk(
    content: str | None = None,
    *,
    reasoning_content: str | None = None,
    reasoning: str | None = None,
) -> _StreamChunk:
    return _StreamChunk(
        _Delta(
            content, reasoning_content=reasoning_content, reasoning=reasoning
        )
    )


def _chunks_from_message(
    content: str,
    *,
    reasoning_content: str | None = None,
    reasoning: str | None = None,
) -> list[_StreamChunk]:
    chunks: list[_StreamChunk] = []
    if reasoning_content:
        chunks.append(_delta_chunk(reasoning_content=reasoning_content))
    elif reasoning:
        chunks.append(_delta_chunk(reasoning=reasoning))
    if content:
        chunks.append(_delta_chunk(content=content))
    if not chunks:
        chunks.append(_delta_chunk(content=""))
    return chunks


class _Completions:
    def __init__(
        self,
        content: str,
        *,
        reasoning_content: str | None = None,
        reasoning: str | None = None,
        chunks: list[_StreamChunk] | None = None,
    ) -> None:
        self.content = content
        self.reasoning_content = reasoning_content
        self.reasoning = reasoning
        self.chunks = chunks
        self.kwargs: list[dict[str, Any]] = []

    async def create(self, **kwargs: Any) -> _ChunkStream:
        self.kwargs.append(kwargs)
        parts = self.chunks
        if parts is None:
            parts = _chunks_from_message(
                self.content,
                reasoning_content=self.reasoning_content,
                reasoning=self.reasoning,
            )
        return _ChunkStream(parts)


class _Chat:
    def __init__(
        self,
        content: str,
        *,
        reasoning_content: str | None = None,
        reasoning: str | None = None,
        chunks: list[_StreamChunk] | None = None,
    ) -> None:
        self.completions = _Completions(
            content,
            reasoning_content=reasoning_content,
            reasoning=reasoning,
            chunks=chunks,
        )


class StubOpenAI:
    def __init__(
        self,
        content: str,
        *,
        reasoning_content: str | None = None,
        reasoning: str | None = None,
        chunks: list[_StreamChunk] | None = None,
    ) -> None:
        self.chat = _Chat(
            content,
            reasoning_content=reasoning_content,
            reasoning=reasoning,
            chunks=chunks,
        )


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
    llm = LlmAdapter(
        Settings(llm_api_key="sk-test", llm_base_url="https://api.x.ai/v1"),
        client=client,
    )
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
    assert "extra_body" not in client.chat.completions.kwargs[0]
    assert client.chat.completions.kwargs[0]["stream"] is True
    assert draft.thinking == ""


def _cited_json() -> str:
    return json.dumps(
        {
            "answer": "last_refresh=x; to_as_of=y. Fuente: texto_ordenado",
            "finding": "obligacion",
            "citations": [{"id": "texto_ordenado", "tipo": "TO"}],
        }
    )


@pytest.mark.asyncio
async def test_adapter_reads_reasoning_content() -> None:
    client = StubOpenAI(_cited_json(), reasoning_content="  pienso el TO  ")
    llm = LlmAdapter(Settings(llm_api_key="sk-test"), client=client)
    draft = await llm.complete("pregunta")
    assert draft.thinking == "pienso el TO"
    assert "Fuente:" in draft.answer
    assert draft.citations[0].id == "texto_ordenado"


@pytest.mark.asyncio
async def test_adapter_reads_string_reasoning() -> None:
    client = StubOpenAI(_cited_json(), reasoning="paso a paso")
    llm = LlmAdapter(Settings(llm_api_key="sk-test"), client=client)
    draft = await llm.complete("pregunta")
    assert draft.thinking == "paso a paso"


@pytest.mark.asyncio
async def test_adapter_strips_think_tags_from_content() -> None:
    body = (
        "<think>\nreviso el dump\n</think>\n\n"
        + _cited_json()
    )
    client = StubOpenAI(body)
    llm = LlmAdapter(Settings(llm_api_key="sk-test"), client=client)
    draft = await llm.complete("pregunta")
    assert draft.thinking == "reviso el dump"
    assert "Fuente:" in draft.answer
    assert "<think>" not in draft.answer


@pytest.mark.asyncio
async def test_adapter_ignores_json_thinking_key() -> None:
    payload = json.dumps(
        {
            "answer": "Fuente: texto_ordenado",
            "finding": "definicion",
            "citations": [{"id": "texto_ordenado", "tipo": "TO"}],
            "thinking": "from json body",
        }
    )
    client = StubOpenAI(payload)
    llm = LlmAdapter(Settings(llm_api_key="sk-test"), client=client)
    draft = await llm.complete("pregunta")
    assert draft.thinking == ""
    assert "from json body" not in draft.answer


def _local_settings(**kwargs: Any) -> Settings:
    return Settings(
        llm_api_key="sk-test",
        llm_base_url="http://127.0.0.1:8001/v1",
        **kwargs,
    )


@pytest.mark.asyncio
async def test_adapter_sends_enable_thinking_by_default_on_local() -> None:
    client = StubOpenAI(_cited_json())
    llm = LlmAdapter(_local_settings(), client=client)
    await llm.complete("pregunta")
    extra = client.chat.completions.kwargs[0]["extra_body"]
    assert extra["enable_thinking"] is True
    assert extra["chat_template_kwargs"]["enable_thinking"] is True


@pytest.mark.asyncio
async def test_adapter_sends_enable_thinking_false_on_local() -> None:
    client = StubOpenAI(_cited_json())
    llm = LlmAdapter(_local_settings(llm_enable_thinking=False), client=client)
    await llm.complete("pregunta")
    extra = client.chat.completions.kwargs[0]["extra_body"]
    assert extra["enable_thinking"] is False
    assert extra["chat_template_kwargs"]["enable_thinking"] is False


@pytest.mark.asyncio
async def test_adapter_streams_reasoning_then_json() -> None:
    payload = _cited_json()
    client = StubOpenAI(
        "",
        chunks=[
            _delta_chunk(reasoning_content="pienso"),
            _delta_chunk(reasoning_content=" el TO"),
            _delta_chunk(content=payload),
        ],
    )
    llm = LlmAdapter(Settings(llm_api_key="sk-test"), client=client)
    seen: list[str] = []

    async def on_thinking(text: str) -> None:
        seen.append(text)

    draft = await llm.complete("pregunta", on_thinking=on_thinking)
    assert seen == ["pienso", "pienso el TO"]
    assert draft.thinking == "pienso el TO"
    assert "Fuente:" in draft.answer
    assert payload not in draft.thinking


@pytest.mark.asyncio
async def test_adapter_splits_think_tags_across_chunks() -> None:
    payload = _cited_json()
    client = StubOpenAI(
        "",
        chunks=[
            _delta_chunk("<thi"),
            _delta_chunk("nk>reviso el dump</th"),
            _delta_chunk("ink>\n\n" + payload),
        ],
    )
    llm = LlmAdapter(Settings(llm_api_key="sk-test"), client=client)
    seen: list[str] = []

    async def on_thinking(text: str) -> None:
        seen.append(text)

    draft = await llm.complete("pregunta", on_thinking=on_thinking)
    assert draft.thinking == "reviso el dump"
    assert seen[-1] == "reviso el dump"
    assert "Fuente:" in draft.answer
    assert payload not in draft.thinking


@pytest.mark.asyncio
async def test_adapter_json_only_stream_does_not_callback_body() -> None:
    payload = _cited_json()
    client = StubOpenAI(payload)
    llm = LlmAdapter(Settings(llm_api_key="sk-test"), client=client)
    seen: list[str] = []

    async def on_thinking(text: str) -> None:
        seen.append(text)

    draft = await llm.complete("pregunta", on_thinking=on_thinking)
    assert seen == []
    assert draft.thinking == ""
    assert "Fuente:" in draft.answer


@pytest.mark.asyncio
async def test_adapter_strips_json_copied_into_reasoning() -> None:
    payload = _cited_json()
    client = StubOpenAI(
        "",
        chunks=[
            _delta_chunk(reasoning_content="pienso el TO\n" + payload),
            _delta_chunk(content=payload),
        ],
    )
    llm = LlmAdapter(Settings(llm_api_key="sk-test"), client=client)
    draft = await llm.complete("pregunta")
    assert "pienso el TO" in draft.thinking
    assert payload not in draft.thinking
    assert "Fuente:" in draft.answer


def test_unwrap_thinking_json_answer_property() -> None:
    clause = (
        "La regla vigente del tipo de cambio de referencia es la establecida "
        "en la Comunicación A 8359, que sustituye el texto de la Comunicación "
        "A 3500 a partir del 02/01/26."
    )
    raw = '{\n"answer": "' + clause + '" }'
    assert unwrap_thinking_text(raw) == clause
    assert unwrap_thinking_text("```json\n" + raw + "\n```") == clause
    assert unwrap_thinking_text('{"answer": "' + clause) == clause
    assert unwrap_thinking_text("{") == ""
    assert unwrap_thinking_text("pienso el TO") == "pienso el TO"


@pytest.mark.asyncio
async def test_adapter_unwraps_json_answer_in_reasoning() -> None:
    clause = (
        "La regla vigente del tipo de cambio de referencia es la establecida "
        "en la Comunicación A 8359, que sustituye el texto de la Comunicación "
        "A 3500 a partir del 02/01/26."
    )
    payload = _cited_json()
    client = StubOpenAI(
        "",
        chunks=[
            _delta_chunk(reasoning_content='{\n"answer": "'),
            _delta_chunk(reasoning_content=clause),
            _delta_chunk(reasoning_content='"\n}'),
            _delta_chunk(content=payload),
        ],
    )
    llm = LlmAdapter(Settings(llm_api_key="sk-test"), client=client)
    seen: list[str] = []

    async def on_thinking(text: str) -> None:
        seen.append(text)

    draft = await llm.complete("pregunta", on_thinking=on_thinking)
    assert draft.thinking == clause
    assert "{" not in draft.thinking
    assert '"answer"' not in draft.thinking
    assert seen
    assert seen[-1] == clause
    assert all("{" not in item and '"answer"' not in item for item in seen)
    assert "Fuente:" in draft.answer
