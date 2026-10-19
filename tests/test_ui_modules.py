"""Tests for the modules split out of the Gradio page: scripts, state, service, stream."""

from __future__ import annotations

import asyncio
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from gradio import Blocks

from bcra_rag.adapters.llm_fake import FakeLlm
from bcra_rag.schemas import ChatResponse
from bcra_rag.ui.auth_js import (
    AUTH_LOGOUT_JS,
    AUTH_REQUEST_JS,
    AUTH_VERIFY_JS,
    fill_placeholders,
)
from bcra_rag.ui.inspector_state import ChatTurnUpdate, InspectorPanels
from bcra_rag.ui.turn_service import TurnService
from bcra_rag.ui.turn_stream import stream_turn_updates
from bcra_rag.use_cases.generate import OnPhase
from tests.chat_fixtures import seed_ready


def test_fill_placeholders_replaces_every_token() -> None:
    template = "const a = __AUTH_A__; const b = __AUTH_B__;"
    assert fill_placeholders(template, {"__AUTH_A__": '"x"', "__AUTH_B__": "2"}) == (
        'const a = "x"; const b = 2;'
    )


def test_fill_placeholders_rejects_value_without_token() -> None:
    with pytest.raises(ValueError, match="not found in template"):
        fill_placeholders("const a = __AUTH_A__;", {"__AUTH_A__": "1", "__AUTH_TYPO__": "2"})


def test_fill_placeholders_rejects_token_without_value() -> None:
    with pytest.raises(ValueError, match="without a value"):
        fill_placeholders("const a = __AUTH_A__; const b = __AUTH_B__;", {"__AUTH_A__": "1"})


def test_rendered_auth_scripts_have_no_placeholders_left() -> None:
    for script in (AUTH_REQUEST_JS, AUTH_VERIFY_JS, AUTH_LOGOUT_JS):
        assert "__AUTH_" not in script


def test_inspector_panels_have_eight_values_in_every_state() -> None:
    for panels in (
        InspectorPanels.cleared(),
        InspectorPanels.pending(),
        InspectorPanels.from_previous(None),
        InspectorPanels.unchanged(),
    ):
        assert len(panels.as_tuple()) == 8


def test_chat_turn_update_puts_session_after_chat_and_phase_last() -> None:
    update = ChatTurnUpdate(
        chat_rows=["rows"],
        session_id="session-1",
        panels=InspectorPanels.cleared(),
        phase_label="phase",
    )
    values = update.as_tuple()
    assert len(values) == 11
    assert values[0] == ["rows"]
    assert values[1] == "session-1"
    assert values[-1] == "phase"


async def test_turn_service_forwards_the_same_collaborators_for_chat_and_clear() -> None:
    captured: list[dict[str, Any]] = []

    async def fake_handle_turn(**kwargs: Any) -> str:
        captured.append(kwargs)
        return "response"

    auth = MagicMock()
    auth.settings.trust_proxy = False
    service = TurnService(
        settings=MagicMock(),
        index=MagicMock(),
        llm=MagicMock(),
        sessions=MagicMock(),
        pipeline=MagicMock(),
        limiter=MagicMock(),
        turn_caps=MagicMock(),
        auth=auth,
    )
    browser_request = SimpleNamespace()
    with (
        patch("bcra_rag.ui.turn_service.handle_turn", fake_handle_turn),
        patch("bcra_rag.ui.turn_service.client_id_for", return_value="client-1"),
    ):
        await service.run_chat_turn(
            gradio_request=browser_request,  # type: ignore[arg-type]
            message="hola",
            session_id="",
            thinking=True,
        )
        await service.run_chat_turn(
            gradio_request=browser_request,  # type: ignore[arg-type]
            message="/clear",
            session_id="session-1",
        )
    chat_call, clear_call = captured
    for name in (
        "settings",
        "index",
        "llm",
        "sessions",
        "pipeline",
        "limiter",
        "turn_caps",
        "auth",
    ):
        assert chat_call[name] is clear_call[name] is getattr(service, name)
    assert chat_call["message"] == "hola"
    assert chat_call["session_id"] is None
    assert chat_call["thinking"] is True
    assert clear_call["message"] == "/clear"
    assert clear_call["session_id"] == "session-1"
    assert clear_call["thinking"] is None
    assert chat_call["client_id"] == clear_call["client_id"] == "client-1"
    assert chat_call["request_id"] != clear_call["request_id"]


class _FatalTurnError(BaseException):
    """An error that is not an Exception, like KeyboardInterrupt but safe in tests."""


async def test_stream_re_raises_errors_that_are_not_exceptions() -> None:
    async def run_turn(*, message, session_id, on_phase=None):  # type: ignore[no-untyped-def]
        del message, session_id, on_phase
        raise _FatalTurnError("stop")

    with pytest.raises(_FatalTurnError):
        async for _ in stream_turn_updates("hola", None, None, run_turn=run_turn):
            pass


async def test_closing_stream_cancels_pending_turn() -> None:
    cancelled = asyncio.Event()

    async def run_turn(
        *, message: str, session_id: str | None, on_phase: OnPhase | None = None
    ) -> ChatResponse:
        assert on_phase is not None
        try:
            await on_phase("generate")
            await asyncio.Event().wait()
        finally:
            cancelled.set()
        raise AssertionError("turn must be cancelled before completion")

    updates = stream_turn_updates("question", None, None, run_turn=run_turn)
    await anext(updates)
    phase = await anext(updates)
    assert phase[-1]["visible"] is True
    await updates.aclose()
    assert cancelled.is_set()


@pytest.fixture
def observatory_blocks(tmp_path: Path) -> tuple[Blocks, FakeLlm]:
    from bcra_rag.adapters.session_memory import InMemorySessionStore
    from bcra_rag.api.rate_limit import RateLimiter
    from bcra_rag.api.turn_caps import TurnCaps
    from bcra_rag.auth import build_auth
    from bcra_rag.composition import default_pipeline
    from bcra_rag.ui.gradio_app import build_observatory_blocks

    settings, index, _ = seed_ready(tmp_path)
    llm = FakeLlm()
    blocks = build_observatory_blocks(
        settings=settings,
        index=index,
        llm=llm,
        sessions=InMemorySessionStore(),
        pipeline=default_pipeline(settings),
        limiter=RateLimiter(max_requests=20, window_s=60),
        turn_caps=TurnCaps(max_email=30, max_process=100),
        auth=build_auth(),
    )
    return blocks, llm


def test_public_endpoint_names_are_unchanged(
    observatory_blocks: tuple[Blocks, FakeLlm],
) -> None:
    blocks, _ = observatory_blocks
    api_names = {str(handler.api_name) for handler in blocks.fns.values()}
    assert {
        "_turn",
        "_turn_1",
        "_clear",
        "_select_card",
        "_layout",
        "_hydrate",
        "_after_auth",
        "_after_logout",
    } <= api_names


def test_suggested_prompts_fill_input_without_running_turn(
    observatory_blocks: tuple[Blocks, FakeLlm],
) -> None:
    from bcra_rag.ui.config import CANNED_PROMPTS

    blocks, llm = observatory_blocks
    fillers = [
        handler
        for handler in blocks.fns.values()
        if handler.fn is not None and handler.fn.__name__ == "<lambda>"
    ]
    assert [handler.fn() for handler in fillers] == list(CANNED_PROMPTS)
    assert all(handler.inputs == [] for handler in fillers)
    assert all(
        len(handler.outputs) == 1 and handler.outputs[0].elem_id == "observatory-input"
        for handler in fillers
    )
    assert llm.calls == []
