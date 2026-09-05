from __future__ import annotations

from pathlib import Path
from typing import Any

import gradio as gr
from fastapi import HTTPException

from bcra_rag.api.handle import client_id_for, demo_key_for, handle_turn
from bcra_rag.api.rate_limit import RateLimiter
from bcra_rag.domain.health import dump_health
from bcra_rag.ports.index import IndexPort
from bcra_rag.ports.llm import LlmPort
from bcra_rag.ports.session import SessionStore
from bcra_rag.settings import Settings
from bcra_rag.ui.config import (
    CANNED_PROMPTS,
    L1_ACCORDION_OPEN_DEFAULT,
    LAYOUT_HELP,
    LAYOUT_STAFF,
    LAYOUT_USER,
    abstain_visible,
    append_messages,
    apply_layout,
    citation_card_markdown,
    citation_cards,
    footer_text,
    freeze_chips_html,
    inspector_payload,
    l1_markdown,
    load_l1,
    title_markdown,
    trust_markdown,
    trust_payload,
)
from bcra_rag.ui.theme import (
    observatory_css_path,
    observatory_head,
    observatory_js,
    observatory_theme,
)
from bcra_rag.use_cases.answer_query import new_request_id


def _choice_update(choices: list[str]) -> Any:
    return gr.update(
        choices=choices,
        value=choices[0] if choices else None,
        visible=bool(choices),
    )


def _copy_update(copy_id: str) -> Any:
    return gr.update(value=copy_id, visible=bool(copy_id))


def _abstain_update(text: str, *, visible: bool) -> Any:
    return gr.update(value=text, visible=visible)


def _empty_inspector() -> tuple[Any, ...]:
    return (
        {},
        [],
        _abstain_update("", visible=False),
        _copy_update(""),
        _choice_update([]),
        [],
        citation_card_markdown(None),
        trust_markdown(None),
    )


def build_blocks(
    *,
    settings: Settings,
    index: IndexPort,
    llm: LlmPort,
    sessions: SessionStore,
    limiter: RateLimiter,
) -> gr.Blocks:
    health = dump_health(settings, index)
    l1_path = Path(settings.evals_dir) / "l1.json"
    l1_data = load_l1(l1_path)

    async def _turn(
        message: str,
        history: list[dict[str, str]],
        session_id: str | None,
        demo_key: str | None,
        request: gr.Request,
    ) -> tuple[Any, ...]:
        history = list(history or [])
        key = (demo_key or "").strip() or demo_key_for(request)
        try:
            response = await handle_turn(
                settings=settings,
                index=index,
                llm=llm,
                sessions=sessions,
                limiter=limiter,
                message=message,
                session_id=session_id or None,
                k=None,
                filters=None,
                request_id=new_request_id(),
                client_id=client_id_for(request),
                demo_key=key or None,
            )
        except HTTPException as exc:
            notice = "Solicitud rechazada."
            if exc.status_code == 401:
                notice = "Se requiere DEMO_API_KEY."
            elif exc.status_code == 429:
                notice = "Demasiadas solicitudes."
            history = append_messages(history, message, notice)
            return (history, session_id, *_empty_inspector())
        history = append_messages(history, message, response.answer)
        cards = citation_cards(response)
        inspector = inspector_payload(response)
        trust = trust_payload(response)
        banner = "Silencio / abstain" if abstain_visible(response) else ""
        copy_id = str(inspector.get("copy_id") or "")
        choices = [str(card["id"]) for card in cards]
        return (
            history,
            response.session_id,
            inspector,
            trust,
            _abstain_update(banner, visible=bool(banner)),
            _copy_update(copy_id),
            _choice_update(choices),
            cards,
            citation_card_markdown(inspector),
            trust_markdown(trust),
        )

    def _clear(
        session_id: str | None,
    ) -> tuple[Any, ...]:
        if session_id:
            sessions.clear(session_id)
        return [], None, *_empty_inspector()

    def _select_card(
        selected: str | None, cards: list[dict[str, Any]]
    ) -> tuple[dict[str, Any], Any, str]:
        if not selected:
            return {}, _copy_update(""), citation_card_markdown(None)
        for card in cards:
            if card.get("id") == selected:
                copy_id = str(card.get("copy_id") or card["id"])
                return card, _copy_update(copy_id), citation_card_markdown(card)
        return {}, _copy_update(""), citation_card_markdown(None)

    with gr.Blocks(title="BCRA Mini-RAG", fill_height=True) as demo:
        session_state = gr.State(None)
        cards_state = gr.State([])
        with gr.Column(elem_id="observatory-shell"):
            with gr.Column(elem_id="observatory-topbar"):
                gr.Markdown(title_markdown(health))
                with gr.Row(elem_id="layout-toggle"):
                    layout_choice = gr.Radio(
                        label="Vista",
                        choices=[LAYOUT_STAFF, LAYOUT_USER],
                        value=LAYOUT_STAFF,
                        container=False,
                        elem_classes=["vista-radio"],
                    )
                    gr.Markdown(LAYOUT_HELP, elem_id="layout-toggle-help")
                freeze_box = gr.HTML(
                    freeze_chips_html(health),
                    elem_id="observatory-freeze",
                    apply_default_css=False,
                    js_on_load="",
                )
            with gr.Row(elem_id="observatory-layout"):
                with gr.Column(scale=3, min_width=0, elem_id="observatory-stage"):
                    abstain_box = gr.Markdown(
                        "",
                        elem_id="abstain-banner",
                        visible=False,
                    )
                    chatbot = gr.Chatbot(
                        label="Chat",
                        show_label=False,
                        height=480,
                        buttons=[],
                        feedback_options=[],
                        placeholder="La conversación aparece acá.",
                    )
                    msg = gr.Textbox(
                        label="Pregunta",
                        placeholder="Preguntá por una cláusula CAMEX…",
                    )
                    with gr.Row(elem_id="observatory-actions"):
                        send = gr.Button("Enviar", variant="primary", scale=0)
                        clear = gr.Button("Clear", variant="secondary", scale=0)
                    demo_box = gr.Textbox(
                        label="Demo key",
                        type="password",
                        visible=bool(settings.demo_api_key),
                    )
                    with gr.Row(elem_id="observatory-pills"):
                        for prompt in CANNED_PROMPTS:
                            pill = gr.Button(
                                prompt,
                                size="sm",
                                scale=0,
                                elem_classes=["observatory-pill"],
                            )
                            pill.click(  # type: ignore[attr-defined]
                                lambda value=prompt: value,
                                outputs=[msg],
                            )
                side = gr.Column(scale=2, min_width=320, elem_id="observatory-side")
                with side:
                    citation_choice = gr.Radio(
                        label="Citas",
                        choices=[],
                        interactive=True,
                        visible=False,
                    )
                    card_md = gr.Markdown(
                        citation_card_markdown(None),
                        elem_id="citation-card",
                    )
                    copy_id = gr.Textbox(
                        label="copy-id",
                        interactive=False,
                        buttons=["copy"],
                        visible=False,
                    )
                    trust_box = gr.HTML(
                        trust_markdown(None),
                        elem_id="trust-panel",
                        apply_default_css=False,
                        js_on_load="",
                    )
                    with gr.Accordion("Calidad L1", open=L1_ACCORDION_OPEN_DEFAULT):
                        gr.Markdown(l1_markdown(l1_data), elem_id="l1-panel")
                    inspector = gr.JSON(label="Citation inspector", visible=False)
                    trust = gr.JSON(label="Trust panel", visible=False)
            gr.Markdown(footer_text(health.last_refresh), elem_id="observatory-footer")

        outputs = [
            chatbot,
            session_state,
            inspector,
            trust,
            abstain_box,
            copy_id,
            citation_choice,
            cards_state,
            card_md,
            trust_box,
        ]
        send.click(  # type: ignore[attr-defined]
            _turn,
            inputs=[msg, chatbot, session_state, demo_box],
            outputs=outputs,
        ).then(lambda: "", outputs=[msg])
        msg.submit(  # type: ignore[attr-defined]
            _turn,
            inputs=[msg, chatbot, session_state, demo_box],
            outputs=outputs,
        ).then(lambda: "", outputs=[msg])
        clear.click(_clear, inputs=[session_state], outputs=outputs)  # type: ignore[attr-defined]
        citation_choice.change(  # type: ignore[attr-defined]
            _select_card,
            inputs=[citation_choice, cards_state],
            outputs=[inspector, copy_id, card_md],
        )
        layout_choice.change(  # type: ignore[attr-defined]
            apply_layout,
            inputs=[layout_choice],
            outputs=[freeze_box, side],
        )
    queued = demo.queue()
    return queued  # type: ignore[no-any-return]


def mount_ui(api: Any, blocks: gr.Blocks) -> Any:
    mounted: Any = gr.mount_gradio_app(
        api,
        blocks,
        path="/",
        theme=observatory_theme(),
        css_paths=observatory_css_path(),
        head=observatory_head(),
        js=observatory_js(),
        footer_links=[],
        run_history=False,
    )
    return mounted
