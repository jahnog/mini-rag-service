from __future__ import annotations

import asyncio
import time
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import suppress
from pathlib import Path
from typing import Any

import gradio as gr
from fastapi import HTTPException

from bcra_rag.api.handle import client_id_for, demo_key_for, handle_turn
from bcra_rag.api.rate_limit import RateLimiter
from bcra_rag.auth import AuthModule, email_from_request
from bcra_rag.domain.guardrails import GuardrailPipeline
from bcra_rag.domain.health import dump_health
from bcra_rag.ports.index import IndexPort
from bcra_rag.ports.llm import LlmPort, OnThinking
from bcra_rag.ports.session import SessionStore
from bcra_rag.schemas import ChatResponse
from bcra_rag.settings import Settings
from bcra_rag.ui.config import (
    AUTH_CODE_LABEL,
    AUTH_EMAIL_LABEL,
    AUTH_LOGOUT,
    AUTH_SEND,
    AUTH_STATUS_GENERIC,
    AUTH_VERIFY,
    CANNED_PROMPTS,
    L1_ACCORDION_OPEN_DEFAULT,
    LAYOUT_HELP,
    LAYOUT_STAFF,
    LAYOUT_USER,
    THOUGHT_PUBLISH_S,
    abstain_visible,
    append_messages,
    append_pending,
    apply_clear_result,
    apply_layout,
    auth_chrome,
    citation_card_markdown,
    citation_cards,
    footer_text,
    freeze_chips_html,
    http_turn_notice,
    inspector_payload,
    l1_markdown,
    load_l1,
    thinking_for_staff,
    thought_publish_ready,
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


TurnRunner = Callable[..., Awaitable[ChatResponse]]

_AUTH_REQUEST_JS = """
async (email) => {
  try {
    const r = await fetch("/auth/request", {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      credentials: "same-origin",
      body: JSON.stringify({email: email || ""}),
    });
    if (r.status === 429) return "Demasiados intentos. Probá más tarde.";
    if (r.status === 503) return "Autenticación no configurada.";
  } catch (e) {}
  return "Si el correo está habilitado, vas a recibir un código.";
}
"""

_AUTH_VERIFY_JS = """
async (email, code) => {
  try {
    const r = await fetch("/auth/verify", {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      credentials: "same-origin",
      body: JSON.stringify({email: email || "", code: code || ""}),
    });
    if (r.ok) return "Sesión iniciada.";
    if (r.status === 429) return "Demasiados intentos. Probá más tarde.";
    return "Código inválido o vencido.";
  } catch (e) {
    return "No se pudo verificar.";
  }
}
"""

_AUTH_LOGOUT_JS = """
async () => {
  try {
    await fetch("/auth/logout", {method: "POST", credentials: "same-origin"});
  } catch (e) {}
  return "Sesión cerrada.";
}
"""


async def iter_observatory_turn(
    message: str,
    history: list[dict[str, Any]] | None,
    session_id: str | None,
    *,
    run_turn: TurnRunner,
    staff: bool = True,
) -> AsyncIterator[tuple[Any, ...]]:
    snapshot = list(history or [])
    started = time.perf_counter()
    yield (append_pending(snapshot, message), session_id, *_skipped_inspector())
    latest = [""]
    held = [""]
    last_pub = [0.0]
    event = asyncio.Event()
    box: list[ChatResponse | BaseException] = []

    async def on_thinking(text: str) -> None:
        held[0] = text
        now = time.monotonic()
        if last_pub[0] == 0.0:
            last_pub[0] = now
        if thought_publish_ready(text) or now - last_pub[0] >= THOUGHT_PUBLISH_S:
            latest[0] = text
            last_pub[0] = now
            event.set()

    async def produce() -> None:
        try:
            box.append(
                await run_turn(
                    message=message,
                    session_id=session_id,
                    on_thinking=on_thinking if staff else None,
                )
            )
        except asyncio.CancelledError:
            raise
        except BaseException as exc:
            box.append(exc)
        finally:
            if held[0]:
                latest[0] = held[0]
            event.set()

    task = asyncio.create_task(produce())
    try:
        while True:
            await event.wait()
            event.clear()
            trace = latest[0]
            if staff and trace:
                yield (
                    append_pending(snapshot, message, thinking=trace),
                    session_id,
                    *_skipped_inspector(),
                )
            if task.done():
                if staff and latest[0] and latest[0] != trace:
                    yield (
                        append_pending(snapshot, message, thinking=latest[0]),
                        session_id,
                        *_skipped_inspector(),
                    )
                break
    finally:
        if not task.done():
            task.cancel()
            with suppress(asyncio.CancelledError):
                await task

    if not box:
        return
    outcome = box[0]
    if isinstance(outcome, HTTPException):
        notice = http_turn_notice(outcome.status_code, str(outcome.detail))
        rows = append_messages(snapshot, message, notice)
        yield (rows, session_id, *_empty_inspector())
        return
    if isinstance(outcome, BaseException):
        raise outcome
    duration = time.perf_counter() - started
    thinking = thinking_for_staff(outcome.thinking, staff=staff)
    rows = append_messages(
        snapshot,
        message,
        outcome.answer,
        thinking=thinking,
        duration=duration,
    )
    cards = citation_cards(outcome) if staff else []
    inspector = inspector_payload(outcome) if staff else {}
    trust = trust_payload(outcome) if staff else []
    banner = "Silencio / abstain" if abstain_visible(outcome) else ""
    copy_id = str(inspector.get("copy_id") or "")
    choices = [str(card["id"]) for card in cards]
    yield (
        rows,
        outcome.session_id,
        inspector,
        trust,
        _abstain_update(banner, visible=bool(banner)),
        _copy_update(copy_id),
        _choice_update(choices),
        cards,
        citation_card_markdown(inspector),
        trust_markdown(trust),
    )


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


def _skipped_inspector() -> tuple[Any, ...]:
    skip = gr.skip()
    return (skip, skip, skip, skip, skip, skip, skip, skip)


def build_blocks(
    *,
    settings: Settings,
    index: IndexPort,
    llm: LlmPort,
    sessions: SessionStore,
    pipeline: GuardrailPipeline,
    limiter: RateLimiter,
    auth: AuthModule,
) -> gr.Blocks:
    health = dump_health(settings, index)
    l1_path = Path(settings.evals_dir) / "l1.json"
    l1_data = load_l1(l1_path)

    async def _turn(
        message: str,
        history: list[dict[str, Any]],
        session_id: str | None,
        demo_key: str | None,
        layout: str | None,
        request: gr.Request,
    ) -> AsyncIterator[tuple[Any, ...]]:
        key = (demo_key or "").strip() or demo_key_for(request)
        staff = (
            email_from_request(auth, request) is not None and layout == LAYOUT_STAFF
        )

        async def run_turn(
            *,
            message: str,
            session_id: str | None,
            on_thinking: OnThinking | None = None,
        ) -> ChatResponse:
            return await handle_turn(
                settings=settings,
                index=index,
                llm=llm,
                sessions=sessions,
                pipeline=pipeline,
                limiter=limiter,
                auth=auth,
                request=request,
                message=message,
                session_id=session_id or None,
                k=None,
                filters=None,
                request_id=new_request_id(),
                client_id=client_id_for(
                    request, trusted_proxy=auth.settings.trust_proxy
                ),
                demo_key=key or None,
                on_thinking=on_thinking,
            )

        async for item in iter_observatory_turn(
            message, history, session_id, run_turn=run_turn, staff=staff
        ):
            yield item

    async def _clear(
        history: list[dict[str, Any]] | None,
        session_id: str | None,
        request: gr.Request,
    ) -> tuple[Any, ...]:
        error: HTTPException | None = None
        try:
            await handle_turn(
                settings=settings,
                index=index,
                llm=llm,
                sessions=sessions,
                pipeline=pipeline,
                limiter=limiter,
                auth=auth,
                request=request,
                message="/clear",
                session_id=session_id or None,
                k=None,
                filters=None,
                request_id=new_request_id(),
                client_id=client_id_for(
                    request, trusted_proxy=auth.settings.trust_proxy
                ),
                demo_key=None,
            )
        except HTTPException as exc:
            error = exc
        rows, sid = apply_clear_result(history, session_id, error)
        return rows, sid, *_empty_inspector()

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
        with gr.Column(
            elem_id="observatory-shell",
            elem_classes=["layout-user"],
        ) as shell:
            with gr.Column(scale=0, elem_id="observatory-topbar"):
                gr.Markdown(title_markdown(health))
                with gr.Column(elem_id="auth-login"):
                    with gr.Row(elem_id="auth-login-fields") as auth_fields:
                        auth_email = gr.Textbox(
                            label=AUTH_EMAIL_LABEL,
                            scale=2,
                            elem_id="auth-email",
                        )
                        send_code = gr.Button(AUTH_SEND, scale=0, elem_id="auth-send")
                        auth_code = gr.Textbox(
                            label=AUTH_CODE_LABEL,
                            scale=1,
                            elem_id="auth-code",
                        )
                        verify_code = gr.Button(
                            AUTH_VERIFY, scale=0, elem_id="auth-verify"
                        )
                    auth_status = gr.Markdown(
                        AUTH_STATUS_GENERIC, elem_id="auth-status"
                    )
                    with gr.Row(elem_id="auth-session", visible=False) as auth_session:
                        auth_who = gr.Markdown("", elem_id="auth-who")
                        logout = gr.Button(AUTH_LOGOUT, scale=0, elem_id="auth-logout")
                with gr.Row(elem_id="layout-toggle"):
                    layout_choice = gr.Radio(
                        label="Vista",
                        choices=[LAYOUT_STAFF, LAYOUT_USER],
                        value=LAYOUT_USER,
                        container=False,
                        elem_classes=["vista-radio"],
                    )
                    gr.Markdown(LAYOUT_HELP, elem_id="layout-toggle-help")
                freeze_box = gr.HTML(
                    freeze_chips_html(health),
                    elem_id="observatory-freeze",
                    apply_default_css=False,
                    js_on_load="",
                    visible=False,
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
                        elem_id="observatory-chat",
                        height="100%",
                        min_height=480,
                        buttons=[],
                        feedback_options=[],
                        placeholder="La conversación aparece acá.",
                        group_consecutive_messages=False,
                    )
                    msg = gr.Textbox(
                        label="Pregunta",
                        show_label=False,
                        lines=1,
                        max_lines=4,
                        placeholder="Preguntá por una cláusula CAMEX…",
                        elem_id="observatory-input",
                    )
                    with gr.Row(elem_id="observatory-actions"):
                        send = gr.Button(
                            "Enviar",
                            variant="primary",
                            scale=0,
                            elem_id="observatory-send",
                        )
                        clear = gr.Button(
                            "Clear", variant="secondary", scale=0, elem_id="observatory-clear"
                        )
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
                side = gr.Column(
                    scale=2, min_width=320, elem_id="observatory-side", visible=False
                )
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
            inputs=[msg, chatbot, session_state, demo_box, layout_choice],
            outputs=outputs,
        ).then(lambda: "", outputs=[msg])
        msg.submit(  # type: ignore[attr-defined]
            _turn,
            inputs=[msg, chatbot, session_state, demo_box, layout_choice],
            outputs=outputs,
        ).then(lambda: "", outputs=[msg])
        clear.click(_clear, inputs=[chatbot, session_state], outputs=outputs)  # type: ignore[attr-defined]
        citation_choice.change(  # type: ignore[attr-defined]
            _select_card,
            inputs=[citation_choice, cards_state],
            outputs=[inspector, copy_id, card_md],
        )

        def _layout(choice: str | None, request: gr.Request) -> tuple[Any, Any, Any]:
            email = email_from_request(auth, request)
            return apply_layout(choice, email is not None)

        def _hydrate(request: gr.Request) -> tuple[Any, ...]:
            email = email_from_request(auth, request)
            authed = email is not None
            freeze, side_u, shell_u = apply_layout(LAYOUT_USER, authed)
            fields, session, who = auth_chrome(authed, email)
            return freeze, side_u, shell_u, fields, session, who, LAYOUT_USER

        def _after_auth(
            choice: str | None, request: gr.Request
        ) -> tuple[Any, ...]:
            email = email_from_request(auth, request)
            authed = email is not None
            freeze, side_u, shell_u = apply_layout(choice, authed)
            fields, session, who = auth_chrome(authed, email)
            return freeze, side_u, shell_u, fields, session, who

        def _after_logout(request: gr.Request) -> tuple[Any, ...]:
            freeze, side_u, shell_u = apply_layout(LAYOUT_USER, False)
            fields, session, who = auth_chrome(False, None)
            return freeze, side_u, shell_u, fields, session, who, LAYOUT_USER

        chrome_out = [freeze_box, side, shell, auth_fields, auth_session, auth_who]
        layout_choice.change(  # type: ignore[attr-defined]
            _layout,
            inputs=[layout_choice],
            outputs=[freeze_box, side, shell],
        )
        demo.load(  # type: ignore[attr-defined]
            _hydrate,
            outputs=[*chrome_out, layout_choice],
        )
        send_code.click(  # type: ignore[attr-defined]
            None,
            inputs=[auth_email],
            outputs=[auth_status],
            js=_AUTH_REQUEST_JS,
        )
        verify_code.click(  # type: ignore[attr-defined]
            None,
            inputs=[auth_email, auth_code],
            outputs=[auth_status],
            js=_AUTH_VERIFY_JS,
        ).then(
            _after_auth,
            inputs=[layout_choice],
            outputs=chrome_out,
        )
        logout.click(  # type: ignore[attr-defined]
            None,
            outputs=[auth_status],
            js=_AUTH_LOGOUT_JS,
        ).then(
            _after_logout,
            outputs=[*chrome_out, layout_choice],
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
