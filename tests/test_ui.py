from __future__ import annotations

from pathlib import Path

import pytest
from fastapi import HTTPException

from bcra_rag.api.rate_limit import RateLimiter
from bcra_rag.schemas import ChatResponse, Finding, GuardrailVerdict, HealthResponse
from bcra_rag.ui.config import (
    AUTH_EMAIL_LABEL,
    AUTH_LOGOUT,
    AUTH_NOTICE,
    AUTH_SEND,
    AUTH_STATUS_GENERIC,
    CANNED_PROMPTS,
    EMPTY_CITATION_CARD,
    EMPTY_TRUST,
    L1_ACCORDION_OPEN_DEFAULT,
    LAYOUT_HELP,
    LAYOUT_STAFF,
    LAYOUT_STAFF_CLASS,
    LAYOUT_USER,
    LAYOUT_USER_CLASS,
    abstain_visible,
    append_messages,
    append_pending,
    apply_clear_result,
    apply_layout,
    banner_markdown,
    citation_card_markdown,
    citation_cards,
    done_thought_title,
    dump_date,
    freeze_chips_html,
    http_turn_notice,
    inspector_payload,
    is_sample_l1,
    l1_markdown,
    layout_updates,
    load_l1,
    thinking_for_staff,
    thought_markdown,
    thought_publish_ready,
    title_markdown,
    topbar_markdown,
    trust_markdown,
    trust_payload,
)
from bcra_rag.ui.gradio_app import (
    _AUTH_REQUEST_JS,
    _AUTH_VERIFY_JS,
    build_blocks,
    iter_observatory_turn,
    mount_ui,
)
from bcra_rag.ui.theme import (
    observatory_css_path,
    observatory_head,
    observatory_js,
    observatory_theme,
)
from tests.chat_fixtures import LAST_REFRESH, TO_AS_OF, make_client, seed_ready


def test_observatory_css_tokens() -> None:
    css = observatory_css_path().read_text(encoding="utf-8")
    assert "#04111d" in css
    assert "#72d6cb" in css
    assert "28px" in css
    assert "color-scheme: dark" in css
    assert ".obs-chip" in css
    assert "#observatory-pills" in css
    assert "#observatory-chat" in css
    assert "overflow: visible" in css
    assert "status-tracker" in css
    assert "flex: 0 0 auto" in css
    assert "flex-wrap: nowrap" in css
    assert 'content: "Citas"' in css
    assert 'content: "Guardrails"' in css
    assert "min-height: 44px" in css
    assert ".thought-group" in css
    assert "thought-pulse" in css
    assert "#observatory-chat .thought-group" in css
    assert ":has(.thought-group)" in css
    assert ".thought-group .content" in css
    assert "layout-user" in css
    assert "#observatory-shell.layout-user .thought-group" in css
    thought_css = "".join(css.split(".thought-group")[1:])
    assert "h1" in thought_css
    assert "0.82rem" in thought_css
    assert "svelte-" not in css.split(".thought-group")[1][:400]


def test_observatory_theme_helpers() -> None:
    path = observatory_css_path()
    assert path.name == "observatory.css"
    assert path.is_file()
    head = observatory_head()
    assert 'name="theme-color"' in head
    assert "#04111d" in head
    assert 'rel="icon"' in head
    assert "data:image/svg+xml" in head
    theme = observatory_theme()
    assert theme is not None
    assert theme.body_background_fill_dark == "#04111d"
    assert "neutral_100" not in str(theme.input_background_fill)
    assert str(theme.button_secondary_text_color).lower() != "black"
    assert "#04111d" in str(theme.body_background_fill)
    js = observatory_js()
    assert "lang = \"es\"" in js or "lang='es'" in js
    assert "classList.add(\"dark\")" in js or "classList.add('dark')" in js


def test_mount_ui_passes_observatory_presentation() -> None:
    from unittest.mock import MagicMock, patch

    api = MagicMock()
    blocks = MagicMock()
    with patch("bcra_rag.ui.gradio_app.gr.mount_gradio_app") as mount:
        mount.return_value = api
        result = mount_ui(api, blocks)
    assert result is api
    kwargs = mount.call_args.kwargs
    assert kwargs["path"] == "/"
    assert kwargs["css_paths"] == observatory_css_path()
    assert kwargs["head"] == observatory_head()
    assert kwargs["footer_links"] == []
    assert kwargs["run_history"] is False
    assert kwargs["theme"] is not None
    assert kwargs["js"] == observatory_js()


def test_append_messages_accepts_none_history() -> None:
    rows = append_messages(None, "hola", "respuesta")
    assert rows == [
        {"role": "user", "content": "hola"},
        {"role": "assistant", "content": "respuesta"},
    ]
    again = append_messages(rows, "y ese punto?", "otra")
    assert len(again) == 4


def test_append_pending_then_done_has_no_leftover_pending() -> None:
    pending = append_pending(None, "hola")
    assert pending[0] == {"role": "user", "content": "hola"}
    assert pending[1]["metadata"]["title"] == "Pensando…"
    assert pending[1]["metadata"]["status"] == "pending"
    growing = append_pending(None, "hola", thinking="voy")
    assert growing[1]["content"] == "voy"
    assert growing[1]["metadata"]["status"] == "pending"
    done = append_messages(
        None, "hola", "Fuente: A8359", thinking="voy a citar", duration=1.4
    )
    statuses = [row.get("metadata", {}).get("status") for row in done]
    assert "pending" not in statuses
    assert "status" not in done[1]["metadata"]
    assert done[1]["content"] == "voy a citar"
    assert "Pensó" in done[1]["metadata"]["title"]
    assert done[2] == {"role": "assistant", "content": "Fuente: A8359"}
    silencio = append_messages(None, "clima", "No puedo responder (scope).")
    assert len(silencio) == 2
    assert "metadata" not in silencio[1]
    denied = append_messages(None, "hola", "Se requiere DEMO_API_KEY.")
    limited = append_messages(None, "hola", "Demasiadas solicitudes.")
    assert "metadata" not in denied[1]
    assert "metadata" not in limited[1]


def test_prior_thoughts_collapse_without_mutating_history() -> None:
    first = append_messages(
        None, "q1", "Fuente: A8359", thinking="trace uno", duration=1
    )
    assert "status" not in first[1]["metadata"]
    second = append_messages(
        first, "q2", "Fuente: A3500", thinking="trace dos", duration=2
    )
    assert first[1]["metadata"].get("status") != "done"
    assert second[1]["metadata"]["status"] == "done"
    assert "status" not in second[4]["metadata"]
    assert second[4]["content"] == "trace dos"
    assert second[5]["content"] == "Fuente: A3500"


def test_thought_publish_ready_waits_for_a_word_break() -> None:
    assert thought_publish_ready("") is False
    assert thought_publish_ready("h") is False
    assert thought_publish_ready("hola") is False
    assert thought_publish_ready("hola ") is True
    assert thought_publish_ready("hola.") is True
    assert thought_publish_ready("hola\n") is True


def test_thought_markdown_does_not_promote_streaming_headings() -> None:
    assert thought_markdown("# ") == "\\# "
    assert thought_markdown("## paso") == "\\## paso"
    assert thought_markdown("voy a citar") == "voy a citar"
    assert thought_markdown("#") == "\\#"
    rows = append_pending(None, "q", thinking="# foo")
    assert rows[1]["content"] == "\\# foo"


def test_done_thought_title_formats_seconds() -> None:
    assert done_thought_title(None) == "Pensó"
    assert done_thought_title(4.2) == "Pensó 4s"
    assert done_thought_title(0.4) == "Pensó 0.4s"


def test_turn_yields_pending_then_result() -> None:
    import inspect

    from bcra_rag.ui import gradio_app

    source = inspect.getsource(gradio_app.build_blocks)
    assert "iter_observatory_turn" in source
    assert "on_thinking" in source


def _turn_response(**kwargs: object) -> ChatResponse:
    payload = {
        "answer": "Fuente: A8359",
        "finding": Finding.DEFINICION,
        "citations": [],
        "abstain": False,
        "last_refresh": LAST_REFRESH,
        "to_as_of": TO_AS_OF,
        "guardrails": [],
        "request_id": "r",
        "session_id": "s1",
        "disclaimer": "x",
        "thinking": "voy a citar",
    }
    payload.update(kwargs)
    return ChatResponse.model_validate(payload)


@pytest.mark.asyncio
async def test_iter_turn_yields_thinking_before_answer() -> None:
    async def run_turn(
        *,
        message: str,
        session_id: str | None,
        on_thinking=None,
    ) -> ChatResponse:
        del message, session_id
        if on_thinking is not None:
            await on_thinking("voy")
            await on_thinking("voy a citar")
        return _turn_response()

    yields: list[tuple[object, ...]] = []
    async for item in iter_observatory_turn(
        "hola", None, None, run_turn=run_turn
    ):
        yields.append(item)
    assert len(yields) >= 3
    first_rows = yields[0][0]
    assert first_rows[1]["metadata"]["status"] == "pending"
    assert first_rows[1]["content"] == ""
    live_rows = [item[0] for item in yields[1:-1]]
    assert live_rows
    assert any("voy" in rows[1]["content"] for rows in live_rows)
    assert all(len(rows) == 2 for rows in live_rows)
    assert all("Fuente:" not in rows[1]["content"] for rows in live_rows)
    final_rows = yields[-1][0]
    assert final_rows[1]["content"] == "voy a citar"
    assert "status" not in final_rows[1]["metadata"]
    assert final_rows[2]["content"] == "Fuente: A8359"
    assert "Fuente:" not in final_rows[1]["content"]


@pytest.mark.asyncio
async def test_iter_turn_publishes_thinking_on_word_breaks() -> None:
    async def run_turn(
        *,
        message: str,
        session_id: str | None,
        on_thinking=None,
    ) -> ChatResponse:
        del message, session_id
        acc = ""
        for char in "hola mundo":
            acc += char
            if on_thinking is not None:
                await on_thinking(acc)
        return _turn_response(thinking="hola mundo")

    yields = [
        item
        async for item in iter_observatory_turn(
            "q", None, None, run_turn=run_turn
        )
    ]
    live = [item[0][1]["content"] for item in yields[1:-1]]
    assert "h" not in live
    assert "ho" not in live
    assert "hol" not in live
    assert any(item.startswith("hola") for item in live)
    assert yields[-1][0][1]["content"] == "hola mundo"


@pytest.mark.asyncio
async def test_iter_turn_http_error_drops_thought() -> None:
    async def run_turn(
        *,
        message: str,
        session_id: str | None,
        on_thinking=None,
    ) -> ChatResponse:
        del message, session_id, on_thinking
        raise HTTPException(status_code=401, detail="invalid demo key")

    yields = [
        item
        async for item in iter_observatory_turn(
            "hola", None, None, run_turn=run_turn
        )
    ]
    final_rows = yields[-1][0]
    assert len(final_rows) == 2
    assert "metadata" not in final_rows[1]
    assert "DEMO_API_KEY" in final_rows[1]["content"]


@pytest.mark.asyncio
async def test_iter_turn_auth_required_spanish_notice() -> None:
    async def run_turn(
        *,
        message: str,
        session_id: str | None,
        on_thinking=None,
    ) -> ChatResponse:
        del message, session_id, on_thinking
        raise HTTPException(status_code=401, detail="authentication required")

    yields = [
        item
        async for item in iter_observatory_turn(
            "hola", None, None, run_turn=run_turn
        )
    ]
    assert AUTH_NOTICE in yields[-1][0][1]["content"]
    assert http_turn_notice(401, "authentication required") == AUTH_NOTICE


def test_clear_while_logged_out_keeps_history_and_shows_notice() -> None:
    history = [
        {"role": "user", "content": "hola"},
        {"role": "assistant", "content": "respuesta"},
    ]
    rows, sid = apply_clear_result(
        history,
        "keep-me",
        HTTPException(status_code=401, detail="authentication required"),
    )
    assert rows[0] == history[0]
    assert rows[1] == history[1]
    assert AUTH_NOTICE in rows[-1]["content"]
    assert sid == "keep-me"


def test_authenticated_clear_empties_conversation() -> None:
    history = [{"role": "user", "content": "hola"}]
    rows, sid = apply_clear_result(history, "s1", None)
    assert rows == []
    assert sid is None


@pytest.mark.asyncio
async def test_iter_turn_usuario_hides_thinking_and_inspector() -> None:
    async def run_turn(
        *,
        message: str,
        session_id: str | None,
        on_thinking=None,
    ) -> ChatResponse:
        del message, session_id
        assert on_thinking is None
        return _turn_response(thinking="trace secreto")

    yields = [
        item
        async for item in iter_observatory_turn(
            "hola", None, None, run_turn=run_turn, staff=False
        )
    ]
    final_rows = yields[-1][0]
    assert all("trace secreto" not in str(row.get("content", "")) for row in final_rows)
    assert yields[-1][2] == {}
    assert thinking_for_staff("trace secreto", staff=False) is None
    assert thinking_for_staff("trace secreto", staff=True) == "trace secreto"


@pytest.mark.asyncio
async def test_iter_turn_silencio_without_thinking_drops_thought() -> None:
    async def run_turn(
        *,
        message: str,
        session_id: str | None,
        on_thinking=None,
    ) -> ChatResponse:
        del message, session_id, on_thinking
        return _turn_response(
            answer="No hay una cláusula citada en el dump CAMEX.",
            finding=Finding.SILENCIO,
            abstain=True,
            abstain_reason="retrieve_empty",
            thinking=None,
        )

    yields = [
        item
        async for item in iter_observatory_turn(
            "clima", None, None, run_turn=run_turn
        )
    ]
    final_rows = yields[-1][0]
    assert len(final_rows) == 2
    assert "metadata" not in final_rows[1]


def test_chatbot_uses_messages_not_tuples() -> None:
    import inspect

    import gradio as gr

    assert "type" not in inspect.signature(gr.Chatbot.__init__).parameters
    assert "Message" in getattr(gr.Chatbot, "data_model").__name__


def test_banner_and_canned_prompts() -> None:
    health = HealthResponse(
        last_refresh=LAST_REFRESH,
        to_as_of=TO_AS_OF,
        last_comm_id="A8464",
        n_docs=10,
        index_ready=True,
    )
    banner = banner_markdown(health)
    topbar = topbar_markdown(health)
    title = title_markdown(health)
    assert TO_AS_OF in banner
    assert LAST_REFRESH in banner
    assert "A8464" in banner
    assert "10" in banner
    assert "no oficial" in banner.lower()
    assert TO_AS_OF in topbar
    assert LAST_REFRESH in topbar
    assert "A8464" in topbar
    assert "10" in topbar
    assert "no oficial" in topbar.lower()
    assert "no oficial" in title.lower()
    assert not title.lstrip().startswith("*")
    assert TO_AS_OF not in title
    assert LAST_REFRESH not in title
    assert "A8464" not in title
    chips = freeze_chips_html(health)
    assert "obs-chip" in chips
    assert TO_AS_OF in chips
    assert LAST_REFRESH in chips
    assert dump_date(LAST_REFRESH) in chips
    assert "A8464" in chips
    assert "10" in chips
    assert dump_date(LAST_REFRESH) == "2026-09-01"
    assert len(CANNED_PROMPTS) == 4
    assert any("A 9999" in p for p in CANNED_PROMPTS)
    assert any("A 3500" in p and "A 8359" in p for p in CANNED_PROMPTS)
    assert any("export" in p.lower() or "liquidar" in p.lower() for p in CANNED_PROMPTS)
    assert any("2001" in p or "2002" in p for p in CANNED_PROMPTS)
    assert L1_ACCORDION_OPEN_DEFAULT is False


def test_l1_fixture_is_labeled_sample(tmp_path: Path) -> None:
    path = Path("evals/l1.json")
    data = load_l1(path)
    assert is_sample_l1(data)
    text = l1_markdown(data)
    assert "unpublished" in text.lower() or "sample" in text.lower()
    lowered = text.lower()
    assert "citation_id_exact" in text or "citation-id" in lowered or "headline" in lowered
    assert "A vs B: A " in text
    assert "'A':" not in text
    assert "{" not in text
    assert "## Retrieval" in text
    assert "## Generation" in text
    assert "skipped" in text.lower()
    assert "faithfulness: 0" not in text.lower()
    empty = load_l1(tmp_path / "missing.json")
    assert is_sample_l1(empty)


def test_l1_markdown_skipped_generation_not_zero() -> None:
    text = l1_markdown(
        {
            "unpublished": False,
            "sample": False,
            "headline_metric": "citation_id_exact",
            "citation_id_exact": None,
            "hit_at_5": 0.8,
            "mrr": 0.5,
            "retrieval": {"skipped": False, "hit_at_5": 0.8, "n": 30},
            "generation": {"skipped": True, "skip_reason": "not_requested", "n": 0},
            "chunking": {"A": 1, "B": 2, "b_documents": ["texto_ordenado"]},
        }
    )
    lowered = text.lower()
    assert "skipped" in lowered
    assert "headline **citation_id_exact**: 0" not in lowered
    assert "headline **citation_id_exact**: none" not in lowered
    assert "faithfulness: 0" not in lowered


def test_l1_markdown_skipped_retrieval_not_zero() -> None:
    text = l1_markdown(
        {
            "unpublished": False,
            "sample": False,
            "headline_metric": "citation_id_exact",
            "citation_id_exact": 0.4,
            "hit_at_5": None,
            "mrr": None,
            "retrieval": {"skipped": True, "skip_reason": "not_requested", "n": 0},
            "generation": {"skipped": False, "citation_id_exact": 0.4, "n": 30},
            "chunking": {"A": 1, "B": 1, "b_documents": ["texto_ordenado"]},
        }
    )
    lowered = text.lower()
    assert "hit@5: skipped" in lowered
    assert "mrr: skipped" in lowered
    assert "hit@5: 0.0" not in lowered
    assert "hit@5: none" not in lowered


def test_inspector_copy_id_and_trust() -> None:
    from bcra_rag.schemas import Citation, Sidecar

    response = ChatResponse(
        answer="Fuente: A8359 last_refresh=x to_as_of=y",
        finding=Finding.DEFINICION,
        citations=[
            Citation(
                id="A8359",
                tipo="A",
                fecha="2025-09-01",
                snippet="tipo de cambio",
                url="https://www.bcra.gob.ar/archivos/Pdfs/comytexord/A8359.pdf",
            )
        ],
        abstain=False,
        last_refresh=LAST_REFRESH,
        to_as_of=TO_AS_OF,
        guardrails=[
            GuardrailVerdict(rule="scope", verdict="pass"),
            GuardrailVerdict(rule="injection", verdict="pass"),
            GuardrailVerdict(rule="no-advice", verdict="pass"),
            GuardrailVerdict(rule="cite-or-abstain", verdict="pass"),
            GuardrailVerdict(rule="freeze-honesty", verdict="pass"),
        ],
        sidecar=Sidecar(),
        request_id="r",
        session_id="s",
        disclaimer="x",
    )
    inspector = inspector_payload(response)
    cards = citation_cards(response)
    assert inspector["copy_id"] == "A8359"
    assert inspector["id"] == "A8359"
    assert cards[0]["id"] == "A8359"
    assert inspector_payload(response, selected_id="A8359")["copy_id"] == "A8359"
    card_md = citation_card_markdown(inspector)
    assert "A8359" in card_md
    assert "bcra.gob.ar" in card_md
    assert "copy-id" in card_md
    assert "bcra.gob.ar" in (inspector["url"] or "")
    trust = trust_payload(response)
    assert all(item["verdict"] == "pass" for item in trust)
    chips = trust_markdown(trust)
    assert "scope" in chips
    assert "pass" in chips
    assert 'class="obs-chip pass"' in chips
    assert "warn" in trust_markdown([{"rule": "x", "verdict": "warn", "detail": ""}])
    assert "block" in trust_markdown([{"rule": "y", "verdict": "block", "detail": ""}])
    assert "obs-chip skipped" in trust_markdown(
        [{"rule": "retrieve", "verdict": "skipped", "detail": "blocked", "stage": "retrieve"}]
    )
    assert "obs-chip redact" in trust_markdown(
        [{"rule": "markdown-sanitize", "verdict": "redact", "detail": "", "stage": "output"}]
    )
    assert 'class="obs-chip warn"' in trust_markdown(
        [{"rule": "x", "verdict": "warn", "detail": ""}]
    )
    assert "not enforced" in trust_markdown(
        [
            {
                "rule": "injection",
                "verdict": "pass",
                "detail": "",
                "enforced": "false",
                "would_block": "true",
            }
        ]
    )
    assert "would-block" in trust_markdown(
        [
            {
                "rule": "injection",
                "verdict": "pass",
                "detail": "",
                "enforced": "false",
                "would_block": "true",
            }
        ]
    )
    assert EMPTY_CITATION_CARD == citation_card_markdown(None)
    assert "obs-empty" in trust_markdown(None)
    assert "guardrails" in EMPTY_TRUST.lower()
    silencio = ChatResponse(
        answer="silencio last_refresh=x to_as_of=y",
        finding=Finding.SILENCIO,
        abstain=True,
        request_id="r",
        session_id="s",
    )
    assert abstain_visible(silencio) is True
    assert abstain_visible(response) is False


def test_session_id_reuse(tmp_path: Path) -> None:
    client, _, _, _ = make_client(tmp_path)
    first = client.post(
        "/chat", json={"message": "qué se exige hoy para liquidar el cobro de exportaciones"}
    ).json()
    second = client.post(
        "/chat",
        json={
            "message": "y ese punto?",
            "session_id": first["session_id"],
        },
    ).json()
    assert first["session_id"] == second["session_id"]


def test_build_blocks_does_not_call_run_l1(tmp_path: Path) -> None:
    from bcra_rag.adapters.llm_fake import FakeLlm
    from bcra_rag.adapters.session_memory import InMemorySessionStore

    settings, index, _ = seed_ready(tmp_path)
    settings = settings.model_copy(update={"evals_dir": Path("evals")})
    llm = FakeLlm()
    from bcra_rag.auth import build_auth
    from bcra_rag.composition import default_pipeline

    blocks = build_blocks(
        settings=settings,
        index=index,
        llm=llm,
        sessions=InMemorySessionStore(),
        pipeline=default_pipeline(settings),
        limiter=RateLimiter(max_requests=20, window_s=60),
        auth=build_auth(),
    )
    assert blocks is not None
    assert llm.calls == []
    assert L1_ACCORDION_OPEN_DEFAULT is False
    ids = _collect_elem_ids(blocks)
    for elem_id in (
        "observatory-shell",
        "observatory-topbar",
        "observatory-layout",
        "observatory-stage",
        "observatory-side",
        "abstain-banner",
        "citation-card",
        "trust-panel",
        "observatory-footer",
        "layout-toggle",
        "layout-toggle-help",
        "auth-login",
        "observatory-freeze",
        "observatory-pills",
        "observatory-chat",
        "observatory-input",
        "observatory-send",
        "observatory-clear",
        "l1-panel",
    ):
        assert elem_id in ids, elem_id
    widgets = list(getattr(blocks, "blocks", {}).values())
    assert not any(type(widget).__name__ == "Examples" for widget in widgets)
    copy_boxes = [
        widget
        for widget in widgets
        if type(widget).__name__ == "Textbox" and getattr(widget, "label", None) == "copy-id"
    ]
    assert copy_boxes
    assert "copy" in (copy_boxes[0].buttons or [])
    assert getattr(copy_boxes[0], "visible", True) is False
    chatbots = [widget for widget in widgets if type(widget).__name__ == "Chatbot"]
    assert chatbots
    assert list(getattr(chatbots[0], "buttons", None) or []) == []
    assert getattr(chatbots[0], "height", None) == "100%"
    assert getattr(chatbots[0], "min_height", None) == 480
    assert getattr(chatbots[0], "group_consecutive_messages", True) is False
    topbar = _widget_by_elem_id(blocks, "observatory-topbar")
    assert topbar is not None
    assert getattr(topbar, "scale", None) == 0
    pregunta = [
        widget
        for widget in widgets
        if type(widget).__name__ == "Textbox" and getattr(widget, "label", None) == "Pregunta"
    ]
    assert pregunta
    assert getattr(pregunta[0], "max_lines", None) == 4
    assert getattr(pregunta[0], "show_label", True) is False
    abstain = _widget_by_elem_id(blocks, "abstain-banner")
    assert abstain is not None
    assert getattr(abstain, "visible", True) is False
    citas = [
        widget
        for widget in widgets
        if type(widget).__name__ == "Radio" and getattr(widget, "label", None) == "Citas"
    ]
    assert citas
    assert getattr(citas[0], "visible", True) is False
    json_widgets = [widget for widget in widgets if type(widget).__name__ == "JSON"]
    assert json_widgets
    assert all(getattr(widget, "visible", True) is False for widget in json_widgets)
    variants = [
        getattr(widget, "variant", None)
        for widget in widgets
        if type(widget).__name__ == "Button"
    ]
    assert "primary" in variants
    assert "secondary" in variants
    freeze = _widget_by_elem_id(blocks, "observatory-freeze")
    side = _widget_by_elem_id(blocks, "observatory-side")
    shell = _widget_by_elem_id(blocks, "observatory-shell")
    assert shell is not None
    assert LAYOUT_USER_CLASS in list(getattr(shell, "elem_classes", None) or [])
    help_box = _widget_by_elem_id(blocks, "layout-toggle-help")
    assert freeze is not None and getattr(freeze, "visible", True) is False
    assert side is not None and getattr(side, "visible", True) is False
    assert help_box is not None
    assert _widget_by_elem_id(blocks, "auth-login") is not None
    radios = [
        widget
        for widget in widgets
        if type(widget).__name__ == "Radio" and getattr(widget, "label", None) == "Vista"
    ]
    assert radios
    vista = radios[0]
    choices = list(getattr(vista, "choices", []) or [])
    choice_vals = [item[0] if isinstance(item, (list, tuple)) else item for item in choices]
    assert LAYOUT_STAFF in choice_vals
    assert LAYOUT_USER in choice_vals
    assert getattr(vista, "value", None) == LAYOUT_USER
    labels = [getattr(widget, "label", None) for widget in widgets]
    assert AUTH_EMAIL_LABEL in labels
    button_vals = [
        getattr(widget, "value", None)
        for widget in widgets
        if type(widget).__name__ == "Button"
    ]
    assert AUTH_SEND in button_vals
    assert AUTH_LOGOUT in button_vals
    css = observatory_css_path().read_text(encoding="utf-8")
    assert "#layout-toggle" in css
    assert "#layout-toggle-help" in css
    assert "#auth-login" in css
    assert AUTH_STATUS_GENERIC


def test_auth_js_posts_token_email_request() -> None:
    assert 'fetch("/auth/request"' in _AUTH_REQUEST_JS
    assert 'JSON.stringify({email: email || ""})' in _AUTH_REQUEST_JS
    assert "credentials: \"same-origin\"" in _AUTH_REQUEST_JS
    assert "if (r.ok)" in _AUTH_REQUEST_JS
    assert "r.status === 403" in _AUTH_REQUEST_JS
    assert "r.status === 422" in _AUTH_REQUEST_JS
    assert 'fetch("/auth/verify"' in _AUTH_VERIFY_JS


def test_layout_toggle_visibility() -> None:
    hide_freeze, hide_side = layout_updates(False)
    show_freeze, show_side = layout_updates(True)
    assert _update_visible(hide_freeze) is False
    assert _update_visible(hide_side) is False
    assert _update_visible(show_freeze) is True
    assert _update_visible(show_side) is True
    user = apply_layout(LAYOUT_USER)
    denied = apply_layout(LAYOUT_STAFF, authenticated=False)
    staff = apply_layout(LAYOUT_STAFF, authenticated=True)
    assert len(user) == 3
    assert len(staff) == 3
    assert _update_visible(user[0]) is False
    assert _update_visible(user[1]) is False
    assert _update_visible(denied[0]) is False
    assert _update_visible(denied[1]) is False
    assert _update_visible(staff[0]) is True
    assert _update_visible(staff[1]) is True
    assert LAYOUT_USER_CLASS in _update_classes(user[2])
    assert LAYOUT_USER_CLASS in _update_classes(denied[2])
    assert LAYOUT_STAFF_CLASS in _update_classes(staff[2])
    assert LAYOUT_STAFF in LAYOUT_HELP
    assert LAYOUT_USER in LAYOUT_HELP
    assert "inspector de citas" in LAYOUT_HELP
    thought_rows = append_messages(None, "q", "Fuente: A8359", thinking="trace")
    assert "status" not in thought_rows[1]["metadata"]
    assert apply_layout(LAYOUT_USER, authenticated=True)[1] is not thought_rows
    assert "Enviar" in LAYOUT_HELP
    help_lines = [line.strip() for line in LAYOUT_HELP.splitlines() if line.strip()]
    assert len(help_lines) == 2
    assert help_lines[0].startswith("Staff")
    assert help_lines[1].startswith("Usuario")


def _update_classes(update: object) -> list[str]:
    if isinstance(update, dict):
        value = update.get("elem_classes")
        return list(value) if isinstance(value, (list, tuple)) else []
    value = getattr(update, "elem_classes", None)
    if isinstance(value, (list, tuple)):
        return list(value)
    payload = getattr(update, "__dict__", {}) or {}
    classes = payload.get("elem_classes")
    return list(classes) if isinstance(classes, (list, tuple)) else []


def _update_visible(update: object) -> bool | None:
    if isinstance(update, dict):
        value = update.get("visible")
        return value if isinstance(value, bool) else None
    value = getattr(update, "visible", None)
    if isinstance(value, bool):
        return value
    payload = getattr(update, "__dict__", {}) or {}
    flag = payload.get("visible")
    return flag if isinstance(flag, bool) else None


def _widget_by_elem_id(blocks: object, elem_id: str) -> object | None:
    mapping = getattr(blocks, "blocks", None)
    if isinstance(mapping, dict):
        for widget in mapping.values():
            if getattr(widget, "elem_id", None) == elem_id:
                return widget
    return None


def _collect_elem_ids(blocks: object) -> set[str]:
    found: set[str] = set()

    def walk(obj: object) -> None:
        if obj is None:
            return
        eid = getattr(obj, "elem_id", None)
        if isinstance(eid, str) and eid:
            found.add(eid)
        if isinstance(obj, dict):
            val = obj.get("elem_id") or obj.get("element_id")
            if isinstance(val, str) and val:
                found.add(val)
            for child in obj.values():
                walk(child)
        elif isinstance(obj, (list, tuple, set)):
            for child in obj:
                walk(child)
        else:
            mapping = getattr(obj, "blocks", None)
            if mapping is not None and mapping is not obj:
                walk(mapping)

    walk(blocks)
    getter = getattr(blocks, "get_config", None)
    if callable(getter):
        walk(getter())
    return found
