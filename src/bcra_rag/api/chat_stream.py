from __future__ import annotations

import asyncio
import contextlib
from collections.abc import AsyncIterator, Coroutine
from typing import Any

from bcra_rag.schemas import ChatResponse

# Reverse proxies (Apache ProxyTimeout) wait for the HTTP status line and then
# for further bytes. POST /chat is one JSON body; thinking does not flush it.
# JSON allows leading whitespace, so newlines keep the proxy from 502-ing.
CHAT_HTTP_HEARTBEAT_S = 10.0


async def json_chat_chunks(
    produce: Coroutine[Any, Any, ChatResponse],
    *,
    heartbeat_s: float | None = None,
) -> AsyncIterator[bytes]:
    interval = CHAT_HTTP_HEARTBEAT_S if heartbeat_s is None else heartbeat_s
    task = asyncio.create_task(produce)
    try:
        yield b"\n"
        while not task.done():
            if interval <= 0:
                await task
                break
            try:
                await asyncio.wait_for(asyncio.shield(task), timeout=interval)
            except TimeoutError:
                yield b"\n"
        yield task.result().model_dump_json().encode("utf-8")
    finally:
        if not task.done():
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await task
