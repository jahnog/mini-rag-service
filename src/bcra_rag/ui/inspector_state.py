"""Named state for the side panels of the page and for one streamed chat update.

Gradio event handlers must return one value per output component, in a fixed
order. `InspectorPanels` and `ChatTurnUpdate` give those positions names and a
single place that turns them into the tuple Gradio expects.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import gradio as gr

from bcra_rag.schemas import ChatResponse
from bcra_rag.ui.config import (
    ABSTAIN_BANNER_TEXT,
    PENDING_CITATION_CARD,
    PENDING_TRUST,
    abstain_visible,
    citation_card_markdown,
    citation_cards,
    inspector_payload,
    trust_markdown,
    trust_payload,
)


def citation_selector_update(choices: list[str], *, selected: str | None = None) -> Any:
    """Update the citation selector: new choices, a valid selection, hidden when empty."""
    return gr.update(
        choices=choices,
        value=selected if selected in choices else (choices[0] if choices else None),
        visible=bool(choices),
    )


def citation_id_box_update(citation_id: str) -> Any:
    """Update the copyable citation id box; hidden when there is no id."""
    return gr.update(value=citation_id, visible=bool(citation_id))


def abstain_banner_update(text: str, *, is_visible: bool) -> Any:
    """Update the "no clause answers this" banner with its text and visibility."""
    return gr.update(value=text, visible=is_visible)


def phase_label_update(text: str) -> Any:
    """Update the pipeline phase label; hidden when the text is empty."""
    return gr.update(value=text, visible=bool(text))


@dataclass(frozen=True)
class PreviousInspectorState:
    """Previous turn's citation card, guardrail rows, cards, and selected id."""

    inspector: dict[str, Any]
    trust: list[dict[str, str]]
    cards: list[dict[str, Any]]
    choice: str | None


@dataclass(frozen=True)
class InspectorPanels:
    """Values for the eight side-panel outputs, in the order Gradio expects.

    Fields are typed `Any` because they hold Gradio update objects, plain data,
    or the `gr.skip()` marker.
    """

    citation_inspector: Any
    guardrail_panel: Any
    abstain_banner: Any
    citation_id_box: Any
    citation_selector: Any
    citation_cards: Any
    citation_card_text: Any
    guardrail_text: Any

    def as_tuple(self) -> tuple[Any, ...]:
        """Return the values in output order."""
        return (
            self.citation_inspector,
            self.guardrail_panel,
            self.abstain_banner,
            self.citation_id_box,
            self.citation_selector,
            self.citation_cards,
            self.citation_card_text,
            self.guardrail_text,
        )

    @classmethod
    def cleared(cls) -> InspectorPanels:
        """Panels with nothing in them, used after a failed turn or a cleared chat."""
        return cls(
            citation_inspector={},
            guardrail_panel=[],
            abstain_banner=abstain_banner_update("", is_visible=False),
            citation_id_box=citation_id_box_update(""),
            citation_selector=citation_selector_update([]),
            citation_cards=[],
            citation_card_text=citation_card_markdown(None),
            guardrail_text=trust_markdown(None),
        )

    @classmethod
    def pending(cls) -> InspectorPanels:
        """Placeholder panels shown while a turn is running."""
        return cls(
            citation_inspector={},
            guardrail_panel=[],
            abstain_banner=abstain_banner_update("", is_visible=False),
            citation_id_box=citation_id_box_update(""),
            citation_selector=citation_selector_update([]),
            citation_cards=[],
            citation_card_text=PENDING_CITATION_CARD,
            guardrail_text=PENDING_TRUST,
        )

    @classmethod
    def from_previous(cls, previous: PreviousInspectorState | None) -> InspectorPanels:
        """Panels as they were before the turn, e.g. after a rate-limit error.

        Falls back to cleared panels when there was nothing to restore.
        """
        if previous is None or (not previous.inspector and not previous.trust):
            return cls.cleared()
        choices = [str(card["id"]) for card in previous.cards]
        return cls(
            citation_inspector=previous.inspector,
            guardrail_panel=previous.trust,
            abstain_banner=abstain_banner_update("", is_visible=False),
            citation_id_box=citation_id_box_update(str(previous.inspector.get("copy_id") or "")),
            citation_selector=citation_selector_update(choices, selected=previous.choice),
            citation_cards=previous.cards,
            citation_card_text=citation_card_markdown(previous.inspector or None),
            guardrail_text=trust_markdown(previous.trust or None),
        )

    @classmethod
    def unchanged(cls) -> InspectorPanels:
        """Tell Gradio to leave every panel as it is.

        Used for streaming updates that only change the chat bubble and phase label.
        """
        skip = gr.skip()
        return cls(skip, skip, skip, skip, skip, skip, skip, skip)

    @classmethod
    def from_response(cls, response: ChatResponse) -> InspectorPanels:
        """Panels for a finished turn: citations, guardrail log, and the abstain banner."""
        cards = citation_cards(response)
        inspector = inspector_payload(response)
        trust = trust_payload(response)
        banner_text = ABSTAIN_BANNER_TEXT if abstain_visible(response) else ""
        choices = [str(card["id"]) for card in cards]
        return cls(
            citation_inspector=inspector,
            guardrail_panel=trust,
            abstain_banner=abstain_banner_update(banner_text, is_visible=bool(banner_text)),
            citation_id_box=citation_id_box_update(str(inspector.get("copy_id") or "")),
            citation_selector=citation_selector_update(choices),
            citation_cards=cards,
            citation_card_text=citation_card_markdown(inspector),
            guardrail_text=trust_markdown(trust),
        )


@dataclass(frozen=True)
class ChatTurnUpdate:
    """One streamed update for the chat page: the chat, the session, the panels, the phase."""

    chat_rows: Any
    session_id: str | None
    panels: InspectorPanels
    phase_label: Any

    def as_tuple(self) -> tuple[Any, ...]:
        """Return the values in the order of the page's output components."""
        return (self.chat_rows, self.session_id, *self.panels.as_tuple(), self.phase_label)
