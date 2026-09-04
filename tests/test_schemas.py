from __future__ import annotations

import pytest
from pydantic import ValidationError

from bcra_rag.schemas import ChatRequest, ChatResponse, Finding, model_has_field


def test_chat_request_rejects_extra_fields() -> None:
    with pytest.raises(ValidationError):
        ChatRequest(message="hola", unexpected=True)  # type: ignore[call-arg]


def test_corpus_as_of_is_not_a_field() -> None:
    assert not model_has_field(ChatRequest, "corpus_as_of")
    assert not model_has_field(ChatResponse, "corpus_as_of")
    with pytest.raises(ValidationError):
        ChatRequest(message="hola", corpus_as_of="2020-01-01")  # type: ignore[call-arg]


def test_abstain_must_match_silencio() -> None:
    with pytest.raises(ValidationError):
        ChatResponse(
            answer="x",
            finding=Finding.DEFINICION,
            abstain=True,
            request_id="r",
            session_id="s",
        )
