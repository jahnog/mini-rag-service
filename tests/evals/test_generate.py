from __future__ import annotations

from pathlib import Path

import pytest

from bcra_rag.adapters.index_fake import FakeIndex
from bcra_rag.adapters.llm_fake import FakeLlm
from bcra_rag.composition import default_pipeline
from bcra_rag.domain.guardrails.types import RailContext
from bcra_rag.domain.models import Chunk
from bcra_rag.settings import Settings
from bcra_rag.use_cases.answer_query import generate_from_context


class _RecordingIndex(FakeIndex):
    pass


@pytest.mark.asyncio
async def test_generate_from_context_does_not_search(tmp_path: Path) -> None:
    index = _RecordingIndex()
    settings = Settings(data_dir=tmp_path)
    hits = [
        Chunk(
            "A3500:1",
            "Tipo de cambio de referencia 2002.",
            {"doc_id": "A3500", "numero": "A3500"},
        )
    ]
    ctx = RailContext(raw="q", text="q", hits=hits, last_refresh="x", to_as_of="A8307")
    result = await generate_from_context(
        FakeLlm(),
        default_pipeline(settings),
        ctx,
        "Qué dice la Comunicación A 3500?",
    )
    assert result.draft is not None
    assert index.search_calls == []
