"""Stream one chat turn to the page: retrieve, generate, verify, then the side panels.

`stream_turn_updates` runs the turn in a background task and yields a page
update whenever the thinking trace or the phase label changes, then one final
update with the answer, citations and guardrail log.
"""

from __future__ import annotations

import asyncio
import time
from collections.abc import AsyncIterator
from contextlib import suppress
from typing import Any, Protocol

import structlog
from fastapi import HTTPException

from bcra_rag.ports.llm import OnThinking
from bcra_rag.schemas import ChatResponse
from bcra_rag.ui.config import (
    PHASE_COPY,
    THOUGHT_PENDING_TITLE,
    THOUGHT_PUBLISH_S,
    TURN_FAILED_NOTICE,
    append_messages,
    append_pending,
    http_turn_notice,
    thinking_for_staff,
    thought_publish_ready,
)
from bcra_rag.ui.inspector_state import (
    ChatTurnUpdate,
    InspectorPanels,
    PreviousInspectorState,
    phase_label_update,
)
from bcra_rag.use_cases.answer_query import OnPhase

_logger = structlog.get_logger("bcra_rag.observatory")


class TurnRunner(Protocol):
    """Runs one chat turn and reports progress through the two callbacks."""

    async def __call__(
        self,
        *,
        message: str,
        session_id: str | None,
        on_thinking: OnThinking | None = None,
        on_phase: OnPhase | None = None,
    ) -> ChatResponse: ...


class TurnProgressTracker:
    """Collects what a turn running in the background reports.

    The turn writes thinking text, phase labels and its final outcome here. The
    streaming loop waits on `update_available` and reads the fields.
    """

    def __init__(self) -> None:
        self.published_thinking = ""  # last thinking text released to the page
        self.latest_received_thinking = ""  # newest thinking text, even if not yet released
        self.last_publish_time = 0.0  # monotonic time of the last release (throttling)
        self.phase_label = ""  # human-readable label of the current phase
        self.turn_outcome: ChatResponse | Exception | None = None
        self.update_available = asyncio.Event()

    async def receive_thinking(self, text: str) -> None:
        """Receive streamed reasoning text and release it to the page at a throttled rate."""
        self.latest_received_thinking = text
        now = time.monotonic()
        # The first chunk starts the throttle clock instead of releasing at once.
        if self.last_publish_time == 0.0:
            self.last_publish_time = now
        seconds_since_publish = now - self.last_publish_time
        # Release when the text ends at a readable boundary and enough time has
        # passed; force a release after twice that interval regardless.
        is_ready = thought_publish_ready(text) and seconds_since_publish >= THOUGHT_PUBLISH_S
        if is_ready or seconds_since_publish >= 2 * THOUGHT_PUBLISH_S:
            self.published_thinking = text
            self.last_publish_time = now
            self.update_available.set()

    async def receive_phase(self, phase_code: str) -> None:
        """Record the pipeline phase (retrieve, generate, verify) and wake the streaming loop."""
        self.phase_label = PHASE_COPY.get(phase_code, "")
        self.update_available.set()
        await self._let_streaming_loop_run()

    async def run_turn_in_background(
        self,
        run_turn: TurnRunner,
        *,
        message: str,
        session_id: str | None,
        is_staff_view: bool,
    ) -> None:
        """Run the turn and store its result or error in `turn_outcome`."""
        try:
            self.turn_outcome = await run_turn(
                message=message,
                session_id=session_id,
                on_thinking=self.receive_thinking if is_staff_view else None,
                on_phase=self.receive_phase,
            )
        except asyncio.CancelledError:
            raise
        except Exception as error:
            # Errors are handed to the streaming loop, which decides how to render them.
            self.turn_outcome = error
        finally:
            # Release any thinking text that was throttled, then wake the loop one
            # last time so it notices the task has finished.
            if self.latest_received_thinking:
                self.published_thinking = self.latest_received_thinking
            self.update_available.set()

    @staticmethod
    async def _let_streaming_loop_run() -> None:
        """Give the streaming loop two scheduler turns to yield the current phase.

        Without this, a fast next phase could replace the label before the page
        ever showed it.
        """
        await asyncio.sleep(0)
        await asyncio.sleep(0)


def _in_progress_update(
    history_snapshot: list[dict[str, Any]],
    message: str,
    session_id: str | None,
    *,
    thinking: str,
    phase_label: str,
) -> ChatTurnUpdate:
    """Update the chat bubble and phase label only; the side panels stay as they are."""
    return ChatTurnUpdate(
        chat_rows=append_pending(
            history_snapshot,
            message,
            thinking=thinking,
            title=phase_label or THOUGHT_PENDING_TITLE,
        ),
        session_id=session_id,
        panels=InspectorPanels.unchanged(),
        phase_label=phase_label_update(phase_label),
    )


async def stream_turn_updates(
    message: str,
    history: list[dict[str, Any]] | None,
    session_id: str | None,
    *,
    run_turn: TurnRunner,
    is_staff_view: bool = True,
    previous_inspector: PreviousInspectorState | None = None,
) -> AsyncIterator[tuple[Any, ...]]:
    """Stream retrieve, generate, and verify, then fill the citation card and guardrail log.

    HTTPException (rate limit and other HTTP errors) restores the previous inspector.
    Any other failure clears the side panel.
    """
    # Copy of the chat history so the caller's list is never mutated.
    history_snapshot = list(history or [])
    started_at = time.perf_counter()

    # 1. Show the user's message at once, with a pending bubble and placeholder panels.
    yield ChatTurnUpdate(
        chat_rows=append_pending(history_snapshot, message),
        session_id=session_id,
        panels=InspectorPanels.pending(),
        phase_label=phase_label_update(""),
    ).as_tuple()

    # 2. Run the turn in the background and stream progress while it works.
    tracker = TurnProgressTracker()
    turn_task = asyncio.create_task(
        tracker.run_turn_in_background(
            run_turn,
            message=message,
            session_id=session_id,
            is_staff_view=is_staff_view,
        )
    )
    last_yielded_thinking = ""
    last_yielded_phase_label = ""
    try:
        # Wake on each event and yield only when the thinking trace or phase
        # changed (the trace is staff-only).
        while True:
            await tracker.update_available.wait()
            tracker.update_available.clear()
            thinking = tracker.published_thinking if is_staff_view else ""
            has_new_thinking = bool(thinking) and thinking != last_yielded_thinking
            has_new_phase = tracker.phase_label != last_yielded_phase_label
            if has_new_thinking or has_new_phase:
                last_yielded_thinking = thinking
                last_yielded_phase_label = tracker.phase_label
                yield _in_progress_update(
                    history_snapshot,
                    message,
                    session_id,
                    thinking=thinking,
                    phase_label=tracker.phase_label,
                ).as_tuple()
            if turn_task.done():
                # Emit the final trace if it was not shown yet, then stop looping.
                final_thinking = tracker.published_thinking if is_staff_view else ""
                if final_thinking and final_thinking != last_yielded_thinking:
                    yield _in_progress_update(
                        history_snapshot,
                        message,
                        session_id,
                        thinking=final_thinking,
                        phase_label=tracker.phase_label,
                    ).as_tuple()
                break
    finally:
        # If the client disconnected or the generator was closed early, cancel
        # the background turn so it does not keep running.
        if not turn_task.done():
            turn_task.cancel()
            with suppress(asyncio.CancelledError):
                await turn_task

    # 3. Turn the outcome into the final page update.
    outcome = tracker.turn_outcome
    if outcome is None:
        # The task ended without storing an outcome: it was cancelled, or it
        # raised something that is not an Exception (e.g. KeyboardInterrupt).
        if turn_task.cancelled():
            return
        turn_task.result()  # re-raises the original error
        return
    if isinstance(outcome, HTTPException):
        # Rate limit and other HTTP errors: show a notice and restore the previous panels.
        yield ChatTurnUpdate(
            chat_rows=append_messages(
                history_snapshot,
                message,
                http_turn_notice(outcome.status_code, str(outcome.detail)),
            ),
            session_id=session_id,
            panels=InspectorPanels.from_previous(previous_inspector),
            phase_label=phase_label_update(""),
        ).as_tuple()
        return
    if isinstance(outcome, Exception):
        # Any other failure: log only the error type, show a generic notice, clear panels.
        _logger.warning("observatory_turn_failed", error=type(outcome).__name__)
        yield ChatTurnUpdate(
            chat_rows=append_messages(history_snapshot, message, TURN_FAILED_NOTICE),
            session_id=session_id,
            panels=InspectorPanels.cleared(),
            phase_label=phase_label_update(""),
        ).as_tuple()
        return
    # Success: build the final chat rows and every panel from the response.
    yield ChatTurnUpdate(
        chat_rows=append_messages(
            history_snapshot,
            message,
            outcome.answer,
            thinking=thinking_for_staff(outcome.thinking, staff=is_staff_view),
            duration=time.perf_counter() - started_at,
        ),
        session_id=outcome.session_id,
        panels=InspectorPanels.from_response(outcome),
        phase_label=phase_label_update(""),
    ).as_tuple()
