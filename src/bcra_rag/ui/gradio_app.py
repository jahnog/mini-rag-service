"""Browser UI for one CAMEX chat turn, the same answer path as POST /chat.

The chat box calls handle_turn. Login is an emailed one-time code or link.
Operador (IA) shows citations, the guardrail log, and the stored Calidad L1
numbers. Usuario hides that column. The phase labels (retrieve, generate,
verify) are progress text, not extra models.

The bubbles on the page are not what a follow-up searches. That memory is
the session store. Usuario turns the model's thinking trace off unless
LLM_THINKING_USER_LAYOUT is set; the trace is not the answer. Calidad L1 is
a file from an offline run. An optional per-turn judge (CHAT_TURN_EVALS, off
by default) can score a finished answer and does not change it.

`build_observatory_blocks` builds the page in three steps: lay out the
widgets, create the event handlers, and wire the handlers to the widgets.
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import gradio as gr
from fastapi import HTTPException

from bcra_rag.api.handle import demo_key_for
from bcra_rag.api.rate_limit import RateLimiter
from bcra_rag.api.turn_caps import TurnCaps
from bcra_rag.auth import AuthModule, email_from_request
from bcra_rag.domain.guardrails import GuardrailPipeline
from bcra_rag.domain.health import dump_health
from bcra_rag.domain.l1_results import L1_FILENAME
from bcra_rag.domain.turn_eval import NoOpTurnEvaluator, TurnEvaluator
from bcra_rag.ports.index import IndexPort
from bcra_rag.ports.llm import LlmPort, OnThinking
from bcra_rag.ports.session import SessionStore
from bcra_rag.schemas import ChatResponse, HealthResponse
from bcra_rag.settings import Settings
from bcra_rag.ui.auth_js import AUTH_LOGOUT_JS, AUTH_VERIFY_JS, auth_request_js
from bcra_rag.ui.config import (
    API_NAME_APPLY_SELECTED_LAYOUT,
    API_NAME_CLEAR_CONVERSATION,
    API_NAME_INITIALIZE_PAGE,
    API_NAME_REFRESH_AFTER_LOGIN,
    API_NAME_RESET_AFTER_LOGOUT,
    API_NAME_SHOW_SELECTED_CITATION,
    API_NAME_SUBMIT_QUESTION,
    AUTH_CLEAR,
    AUTH_CODE_LABEL,
    AUTH_EMAIL_LABEL,
    AUTH_KICKER,
    AUTH_LOGOUT,
    AUTH_SEND,
    AUTH_STATUS_GENERIC,
    AUTH_VERIFY,
    CANNED_PROMPTS,
    CHAT_KICKER,
    CHAT_LABEL,
    CHAT_PLACEHOLDER,
    CITATION_CHOICE_LABEL,
    CITATION_ID_LABEL,
    CITATIONS_KICKER,
    CODE_PLACEHOLDER,
    DEMO_KEY_LABEL,
    EMAIL_PLACEHOLDER,
    EXAMPLES_KICKER,
    GUARDRAILS_JSON_LABEL,
    GUARDRAILS_KICKER,
    INSPECTOR_JSON_LABEL,
    L1_ACCORDION_LABEL,
    L1_ACCORDION_OPEN_DEFAULT,
    LAYOUT_CHOICE_LABEL,
    LAYOUT_HELP,
    LAYOUT_STAFF,
    LAYOUT_USER,
    QUESTION_LABEL,
    QUESTION_PLACEHOLDER,
    SEND_BUTTON_LABEL,
    apply_clear_result,
    apply_layout,
    auth_chrome,
    auth_status_smtp_ok,
    citation_card_markdown,
    footer_text,
    freeze_chips_html,
    l1_markdown,
    load_l1,
    thinking_for_layout,
    trust_markdown,
)
from bcra_rag.ui.inspector_state import (
    InspectorPanels,
    PreviousInspectorState,
    citation_id_box_update,
    phase_label_update,
)
from bcra_rag.ui.theme import PAGE_TITLE, footer_html, topbar_html
from bcra_rag.ui.turn_service import TurnService
from bcra_rag.ui.turn_stream import stream_turn_updates
from bcra_rag.use_cases.answer_query import OnPhase

# ---------------------------------------------------------------------------
# Widgets
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class LoginWidgets:
    """The sign-in card and the view toggle."""

    fields_row: Any
    email_box: Any
    send_code_button: Any
    code_box: Any
    verify_code_button: Any
    status: Any
    session_row: Any
    signed_in_email_label: Any
    logout_button: Any
    layout_choice: Any
    freeze_chips_box: Any


@dataclass(frozen=True)
class ChatStageWidgets:
    """The main column: abstain banner, chat, example prompts and the composer."""

    abstain_banner: Any
    chatbot: Any
    phase_label_box: Any
    example_prompt_buttons: list[Any]
    question_box: Any
    send_button: Any
    clear_button: Any
    demo_key_box: Any


@dataclass(frozen=True)
class StaffSidePanelWidgets:
    """The staff column: citations, guardrail log and the stored Calidad L1 numbers."""

    panel: Any
    citation_selector: Any
    citation_card_box: Any
    citation_id_box: Any
    guardrail_panel_html: Any
    citation_inspector_json: Any
    guardrail_panel_json: Any


@dataclass(frozen=True)
class PageWidgets:
    """Every widget the event wiring needs."""

    session_state: Any
    cards_state: Any
    page_shell: Any
    login: LoginWidgets
    stage: ChatStageWidgets
    side_panel: StaffSidePanelWidgets


def _build_login_area(health: HealthResponse) -> LoginWidgets:
    """Sign-in card (email, code, status, session row) and the Operador/Usuario toggle."""
    with gr.Column(elem_id="auth-login"):
        gr.Markdown(AUTH_KICKER, elem_id="auth-kicker")
        with gr.Row(elem_id="auth-login-fields") as fields_row:
            email_box = gr.Textbox(
                label=AUTH_EMAIL_LABEL,
                placeholder=EMAIL_PLACEHOLDER,
                scale=2,
                elem_id="auth-email",
            )
            send_code_button = gr.Button(AUTH_SEND, scale=0, elem_id="auth-send")
            code_box = gr.Textbox(
                label=AUTH_CODE_LABEL,
                placeholder=CODE_PLACEHOLDER,
                scale=1,
                elem_id="auth-code",
            )
            verify_code_button = gr.Button(AUTH_VERIFY, scale=0, elem_id="auth-verify")
        status = gr.Markdown(AUTH_STATUS_GENERIC, elem_id="auth-status")
        with gr.Row(elem_id="auth-session", visible=False) as session_row:
            signed_in_email_label = gr.Markdown("", elem_id="auth-who")
            logout_button = gr.Button(AUTH_LOGOUT, scale=0, elem_id="auth-logout")
        with gr.Row(elem_id="layout-toggle"):
            layout_choice = gr.Radio(
                label=LAYOUT_CHOICE_LABEL,
                choices=[LAYOUT_STAFF, LAYOUT_USER],
                value=LAYOUT_USER,
                container=False,
                elem_classes=["vista-radio"],
            )
            gr.Markdown(LAYOUT_HELP, elem_id="layout-toggle-help")
        freeze_chips_box = gr.HTML(
            freeze_chips_html(health),
            elem_id="observatory-freeze",
            apply_default_css=False,
            js_on_load="",
            visible=False,
        )
    return LoginWidgets(
        fields_row=fields_row,
        email_box=email_box,
        send_code_button=send_code_button,
        code_box=code_box,
        verify_code_button=verify_code_button,
        status=status,
        session_row=session_row,
        signed_in_email_label=signed_in_email_label,
        logout_button=logout_button,
        layout_choice=layout_choice,
        freeze_chips_box=freeze_chips_box,
    )


def _build_chat_stage(settings: Settings) -> ChatStageWidgets:
    """Abstain banner, chat, phase label, example prompts and the one-line composer."""
    with gr.Column(scale=3, min_width=0, elem_id="observatory-stage"):
        abstain_banner = gr.Markdown("", elem_id="abstain-banner", visible=False)
        gr.Markdown(CHAT_KICKER, elem_id="chat-kicker")
        chatbot = gr.Chatbot(
            label=CHAT_LABEL,
            show_label=False,
            elem_id="observatory-chat",
            height="auto",
            min_height=192,
            buttons=[],
            feedback_options=[],
            placeholder=CHAT_PLACEHOLDER,
            group_consecutive_messages=False,
        )
        phase_label_box = gr.Markdown("", elem_id="turn-phase", visible=False)
        # Examples sit above the composer; the composer is one line (question,
        # Enviar, Limpiar) and sticks to the viewport bottom on desktop.
        gr.Markdown(EXAMPLES_KICKER, elem_id="examples-kicker")
        with gr.Row(elem_id="observatory-pills"):
            example_prompt_buttons = [
                gr.Button(
                    prompt,
                    size="sm",
                    scale=0,
                    elem_classes=["observatory-pill"],
                )
                for prompt in CANNED_PROMPTS
            ]
        with gr.Row(elem_id="observatory-composer"):
            question_box = gr.Textbox(
                label=QUESTION_LABEL,
                lines=1,
                max_lines=4,
                placeholder=QUESTION_PLACEHOLDER,
                scale=1,
                elem_id="observatory-input",
            )
            send_button = gr.Button(
                SEND_BUTTON_LABEL,
                variant="primary",
                scale=0,
                elem_id="observatory-send",
            )
            clear_button = gr.Button(
                AUTH_CLEAR, variant="secondary", scale=0, elem_id="observatory-clear"
            )
        demo_key_box = gr.Textbox(
            label=DEMO_KEY_LABEL,
            type="password",
            visible=bool(settings.demo_api_key),
        )
    return ChatStageWidgets(
        abstain_banner=abstain_banner,
        chatbot=chatbot,
        phase_label_box=phase_label_box,
        example_prompt_buttons=example_prompt_buttons,
        question_box=question_box,
        send_button=send_button,
        clear_button=clear_button,
        demo_key_box=demo_key_box,
    )


def _build_staff_side_panel(l1_results: dict[str, Any]) -> StaffSidePanelWidgets:
    """Staff column: citations, guardrail log, and Calidad L1.

    L1 is evals/l1.json, read once while these blocks were built.
    """
    panel = gr.Column(scale=2, min_width=320, elem_id="observatory-side", visible=False)
    with panel:
        citation_selector = gr.Radio(
            label=CITATION_CHOICE_LABEL,
            choices=[],
            interactive=True,
            visible=False,
        )
        gr.Markdown(CITATIONS_KICKER, elem_id="citations-kicker")
        citation_card_box = gr.Markdown(
            citation_card_markdown(None),
            elem_id="citation-card",
        )
        citation_id_box = gr.Textbox(
            label=CITATION_ID_LABEL,
            interactive=False,
            buttons=["copy"],
            visible=False,
        )
        gr.Markdown(GUARDRAILS_KICKER, elem_id="guardrails-kicker")
        guardrail_panel_html = gr.HTML(
            trust_markdown(None),
            elem_id="trust-panel",
            apply_default_css=False,
            js_on_load="",
        )
        with gr.Accordion(L1_ACCORDION_LABEL, open=L1_ACCORDION_OPEN_DEFAULT):
            gr.Markdown(l1_markdown(l1_results), elem_id="l1-panel")
        citation_inspector_json = gr.JSON(label=INSPECTOR_JSON_LABEL, visible=False)
        guardrail_panel_json = gr.JSON(label=GUARDRAILS_JSON_LABEL, visible=False)
    return StaffSidePanelWidgets(
        panel=panel,
        citation_selector=citation_selector,
        citation_card_box=citation_card_box,
        citation_id_box=citation_id_box,
        guardrail_panel_html=guardrail_panel_html,
        citation_inspector_json=citation_inspector_json,
        guardrail_panel_json=guardrail_panel_json,
    )


def _build_layout(
    settings: Settings, health: HealthResponse, l1_results: dict[str, Any]
) -> PageWidgets:
    """Create every widget: topbar, sign-in card, chat stage, staff column, footer."""
    session_state = gr.State(None)
    cards_state = gr.State([])
    with gr.Column(elem_id="observatory-shell", elem_classes=["layout-user"]) as page_shell:
        # Family chrome: static topbar, then the sign-in card, then the
        # stage and side panels, then the family footer.
        gr.HTML(
            topbar_html(),
            elem_id="observatory-topbar",
            apply_default_css=False,
            js_on_load="",
        )
        login = _build_login_area(health)
        with gr.Row(elem_id="observatory-layout"):
            stage = _build_chat_stage(settings)
            side_panel = _build_staff_side_panel(l1_results)
        gr.HTML(
            footer_html(footer_text(health.last_refresh)),
            elem_id="observatory-footer-host",
            apply_default_css=False,
            js_on_load="",
        )
    return PageWidgets(
        session_state=session_state,
        cards_state=cards_state,
        page_shell=page_shell,
        login=login,
        stage=stage,
        side_panel=side_panel,
    )


# ---------------------------------------------------------------------------
# Handlers
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class PageHandlers:
    """The functions Gradio calls when the user acts on the page."""

    submit_question: Callable[..., AsyncIterator[tuple[Any, ...]]]
    clear_conversation: Callable[..., Any]
    show_selected_citation: Callable[..., tuple[dict[str, Any], Any, str]]
    apply_selected_layout: Callable[..., tuple[Any, Any, Any]]
    initialize_page_on_load: Callable[..., tuple[Any, ...]]
    refresh_chrome_after_login: Callable[..., tuple[Any, ...]]
    reset_chrome_after_logout: Callable[..., tuple[Any, ...]]


def show_selected_citation(
    selected_citation_id: str | None, cards: list[dict[str, Any]]
) -> tuple[dict[str, Any], Any, str]:
    """Show the citation card picked in the selector, or an empty card if none matches."""
    if not selected_citation_id:
        return {}, citation_id_box_update(""), citation_card_markdown(None)
    for card in cards:
        if card.get("id") == selected_citation_id:
            citation_id = str(card.get("copy_id") or card["id"])
            return card, citation_id_box_update(citation_id), citation_card_markdown(card)
    return {}, citation_id_box_update(""), citation_card_markdown(None)


def _chrome_updates(selected_layout: str | None, email: str | None) -> tuple[Any, ...]:
    """Layout and sign-in widget updates for a visitor, in `auth_chrome_outputs` order.

    The order is: freeze chips, staff side panel, page shell, login fields,
    session row, signed-in label.
    """
    is_signed_in = email is not None
    freeze_chips, side_panel, page_shell = apply_layout(selected_layout, is_signed_in)
    login_fields, session_row, signed_in_label = auth_chrome(is_signed_in, email)
    return freeze_chips, side_panel, page_shell, login_fields, session_row, signed_in_label


def _make_page_handlers(
    service: TurnService, auth: AuthModule, settings: Settings
) -> PageHandlers:
    """Create the handlers that need the turn service, auth, or settings."""

    async def submit_question(
        question: str,
        chat_history: list[dict[str, Any]],
        session_id: str | None,
        typed_demo_key: str | None,
        selected_layout: str | None,
        previous_inspector_json: dict[str, Any] | None,
        previous_guardrail_rows: list[dict[str, str]] | None,
        previous_cards: list[dict[str, Any]] | None,
        previous_citation_choice: str | None,
        gradio_request: gr.Request,
    ) -> AsyncIterator[tuple[Any, ...]]:
        """Submit handler: run one chat turn and stream UI updates to the page."""
        # Prefer an explicit demo key; otherwise derive one from the request.
        demo_key = (typed_demo_key or "").strip() or demo_key_for(gradio_request)
        previous_inspector = PreviousInspectorState(
            inspector=dict(previous_inspector_json or {}),
            trust=list(previous_guardrail_rows or []),
            cards=list(previous_cards or []),
            choice=previous_citation_choice,
        )
        # Staff view requires both a signed-in user and the staff layout selected.
        is_staff_view = (
            email_from_request(auth, gradio_request) is not None
            and selected_layout == LAYOUT_STAFF
        )

        async def run_turn(
            *,
            message: str,
            session_id: str | None,
            on_thinking: OnThinking | None = None,
            on_phase: OnPhase | None = None,
        ) -> ChatResponse:
            """Run the turn through the same `handle_turn` path as POST /chat."""
            return await service.run_chat_turn(
                gradio_request=gradio_request,
                message=message,
                session_id=session_id,
                demo_key=demo_key or None,
                thinking=thinking_for_layout(is_staff_view, settings),
                on_thinking=on_thinking,
                on_phase=on_phase,
            )

        async for page_update in stream_turn_updates(
            question,
            chat_history,
            session_id,
            run_turn=run_turn,
            is_staff_view=is_staff_view,
            previous_inspector=previous_inspector,
        ):
            yield page_update

    async def clear_conversation(
        chat_history: list[dict[str, Any]] | None,
        session_id: str | None,
        gradio_request: gr.Request,
    ) -> tuple[Any, ...]:
        """Clear button handler: send `/clear` to the backend and reset the chat and panels.

        An HTTP error from the backend is passed to `apply_clear_result`, which
        decides what the chat shows.
        """
        backend_error: HTTPException | None = None
        try:
            await service.run_chat_turn(
                gradio_request=gradio_request,
                message="/clear",
                session_id=session_id,
                demo_key=None,
            )
        except HTTPException as error:
            backend_error = error
        chat_rows, new_session_id = apply_clear_result(chat_history, session_id, backend_error)
        return (
            chat_rows,
            new_session_id,
            *InspectorPanels.cleared().as_tuple(),
            phase_label_update(""),
        )

    def apply_selected_layout(
        selected_layout: str | None, gradio_request: gr.Request
    ) -> tuple[Any, Any, Any]:
        """Apply the chosen layout (user or staff) given whether the visitor is signed in."""
        email = email_from_request(auth, gradio_request)
        return apply_layout(selected_layout, email is not None)

    def initialize_page_on_load(gradio_request: gr.Request) -> tuple[Any, ...]:
        """On page load: set the user layout and auth widgets from the session cookie."""
        email = email_from_request(auth, gradio_request)
        return (*_chrome_updates(LAYOUT_USER, email), LAYOUT_USER)

    def refresh_chrome_after_login(
        selected_layout: str | None, gradio_request: gr.Request
    ) -> tuple[Any, ...]:
        """After code verification: refresh layout and auth widgets for the new session."""
        email = email_from_request(auth, gradio_request)
        return _chrome_updates(selected_layout, email)

    def reset_chrome_after_logout() -> tuple[Any, ...]:
        """After logout: reset to the signed-out user layout and auth widgets."""
        return (*_chrome_updates(LAYOUT_USER, None), LAYOUT_USER)

    return PageHandlers(
        submit_question=submit_question,
        clear_conversation=clear_conversation,
        show_selected_citation=show_selected_citation,
        apply_selected_layout=apply_selected_layout,
        initialize_page_on_load=initialize_page_on_load,
        refresh_chrome_after_login=refresh_chrome_after_login,
        reset_chrome_after_logout=reset_chrome_after_logout,
    )


# ---------------------------------------------------------------------------
# Wiring
# ---------------------------------------------------------------------------


def _empty_text() -> str:
    """Empty string, used to clear the question box after a submit."""
    return ""


def _wire_events(
    observatory_blocks: gr.Blocks,
    widgets: PageWidgets,
    handlers: PageHandlers,
    auth: AuthModule,
) -> None:
    """Connect every widget event to its handler or browser script."""
    login = widgets.login
    stage = widgets.stage
    side_panel = widgets.side_panel

    # The order of these lists must match the values `ChatTurnUpdate.as_tuple` returns.
    turn_outputs = [
        stage.chatbot,
        widgets.session_state,
        side_panel.citation_inspector_json,
        side_panel.guardrail_panel_json,
        stage.abstain_banner,
        side_panel.citation_id_box,
        side_panel.citation_selector,
        widgets.cards_state,
        side_panel.citation_card_box,
        side_panel.guardrail_panel_html,
        stage.phase_label_box,
    ]
    turn_inputs = [
        stage.question_box,
        stage.chatbot,
        widgets.session_state,
        stage.demo_key_box,
        login.layout_choice,
        side_panel.citation_inspector_json,
        side_panel.guardrail_panel_json,
        widgets.cards_state,
        side_panel.citation_selector,
    ]
    # The order must match the values `_chrome_updates` returns.
    auth_chrome_outputs = [
        login.freeze_chips_box,
        side_panel.panel,
        widgets.page_shell,
        login.fields_row,
        login.session_row,
        login.signed_in_email_label,
    ]

    # Chat: the Enviar button and pressing Enter both submit the question.
    submit_triggers = (
        stage.send_button.click,  # type: ignore[attr-defined]
        stage.question_box.submit,  # type: ignore[attr-defined]
    )
    for submit_trigger in submit_triggers:
        submit_trigger(
            handlers.submit_question,
            inputs=turn_inputs,
            outputs=turn_outputs,
            api_name=API_NAME_SUBMIT_QUESTION,
        ).then(_empty_text, outputs=[stage.question_box])
    stage.clear_button.click(  # type: ignore[attr-defined]
        handlers.clear_conversation,
        inputs=[stage.chatbot, widgets.session_state],
        outputs=turn_outputs,
        api_name=API_NAME_CLEAR_CONVERSATION,
    )
    for example_button, example_prompt in zip(
        stage.example_prompt_buttons, CANNED_PROMPTS, strict=True
    ):
        example_button.click(  # type: ignore[attr-defined]
            lambda prompt=example_prompt: prompt,
            outputs=[stage.question_box],
        )

    # Staff column and layout toggle.
    side_panel.citation_selector.change(  # type: ignore[attr-defined]
        handlers.show_selected_citation,
        inputs=[side_panel.citation_selector, widgets.cards_state],
        outputs=[
            side_panel.citation_inspector_json,
            side_panel.citation_id_box,
            side_panel.citation_card_box,
        ],
        api_name=API_NAME_SHOW_SELECTED_CITATION,
    )
    login.layout_choice.change(  # type: ignore[attr-defined]
        handlers.apply_selected_layout,
        inputs=[login.layout_choice],
        outputs=[login.freeze_chips_box, side_panel.panel, widgets.page_shell],
        api_name=API_NAME_APPLY_SELECTED_LAYOUT,
    )
    observatory_blocks.load(  # type: ignore[attr-defined]
        handlers.initialize_page_on_load,
        outputs=[*auth_chrome_outputs, login.layout_choice],
        api_name=API_NAME_INITIALIZE_PAGE,
    )

    # Login: the browser scripts call the auth routes; the handlers refresh the page after.
    login.send_code_button.click(  # type: ignore[attr-defined]
        None,
        inputs=[login.email_box],
        outputs=[login.status],
        js=auth_request_js(auth_status_smtp_ok(auth.settings.otp_ttl_s)),
    )
    login.verify_code_button.click(  # type: ignore[attr-defined]
        None,
        inputs=[login.email_box, login.code_box],
        outputs=[login.status],
        js=AUTH_VERIFY_JS,
    ).then(
        handlers.refresh_chrome_after_login,
        inputs=[login.layout_choice],
        outputs=auth_chrome_outputs,
        api_name=API_NAME_REFRESH_AFTER_LOGIN,
    )
    login.logout_button.click(  # type: ignore[attr-defined]
        None,
        outputs=[login.status],
        js=AUTH_LOGOUT_JS,
    ).then(
        handlers.reset_chrome_after_logout,
        outputs=[*auth_chrome_outputs, login.layout_choice],
        api_name=API_NAME_RESET_AFTER_LOGOUT,
    )


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def build_observatory_blocks(
    *,
    settings: Settings,
    index: IndexPort,
    llm: LlmPort,
    sessions: SessionStore,
    pipeline: GuardrailPipeline,
    limiter: RateLimiter,
    turn_caps: TurnCaps,
    auth: AuthModule,
    turn_evaluator: TurnEvaluator | None = None,
) -> gr.Blocks:
    """Build the widgets and wire submit to handle_turn, the same path as POST /chat."""
    health = dump_health(settings, index)
    l1_results = load_l1(Path(settings.evals_dir) / L1_FILENAME)
    service = TurnService(
        settings=settings,
        index=index,
        llm=llm,
        sessions=sessions,
        pipeline=pipeline,
        limiter=limiter,
        turn_caps=turn_caps,
        auth=auth,
        turn_evaluator=turn_evaluator or NoOpTurnEvaluator(),
    )
    handlers = _make_page_handlers(service, auth, settings)

    with gr.Blocks(title=PAGE_TITLE) as observatory_blocks:
        widgets = _build_layout(settings, health, l1_results)
        _wire_events(observatory_blocks, widgets, handlers, auth)
    queued = observatory_blocks.queue()
    return queued  # type: ignore[no-any-return]
