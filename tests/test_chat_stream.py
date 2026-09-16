from __future__ import annotations

import asyncio
import json

from bcra_rag.api.chat_stream import json_chat_chunks
from bcra_rag.schemas import ChatResponse, Finding

_SAMPLE = ChatResponse(
    answer="ok",
    finding=Finding.DEFINICION,
    abstain=False,
    request_id="r",
    session_id="s",
)


async def test_json_chunks_flush_then_body() -> None:
    async def produce() -> ChatResponse:
        return _SAMPLE

    chunks = [chunk async for chunk in json_chat_chunks(produce(), heartbeat_s=1.0)]
    assert chunks[0] == b"\n"
    assert json.loads(b"".join(chunks))["answer"] == "ok"
    assert chunks[-1].startswith(b"{")


async def test_json_chunks_no_heartbeat_when_interval_non_positive() -> None:
    async def produce() -> ChatResponse:
        await asyncio.sleep(0.02)
        return _SAMPLE

    chunks = [chunk async for chunk in json_chat_chunks(produce(), heartbeat_s=0)]
    assert chunks == [b"\n", _SAMPLE.model_dump_json().encode("utf-8")]


async def test_json_chunks_heartbeat_while_waiting() -> None:
    async def produce() -> ChatResponse:
        await asyncio.sleep(0.12)
        return _SAMPLE

    chunks = [chunk async for chunk in json_chat_chunks(produce(), heartbeat_s=0.05)]
    assert chunks[0] == b"\n"
    assert chunks.count(b"\n") >= 3
    body = json.loads(b"".join(chunks))
    assert body["finding"] == "definicion"
    assert body["session_id"] == "s"


async def test_json_chunks_cancel_producer_on_aclose() -> None:
    started = asyncio.Event()
    cancelled = asyncio.Event()

    async def produce() -> ChatResponse:
        started.set()
        try:
            await asyncio.sleep(10)
        except asyncio.CancelledError:
            cancelled.set()
            raise
        return _SAMPLE

    gen = json_chat_chunks(produce(), heartbeat_s=0.05)
    assert await gen.__anext__() == b"\n"
    await started.wait()
    await gen.aclose()
    assert cancelled.is_set()
