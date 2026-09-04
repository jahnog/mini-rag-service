from __future__ import annotations

from pathlib import Path

from bcra_rag.api.rate_limit import RateLimiter
from bcra_rag.schemas import ChatResponse, Finding, GuardrailVerdict, HealthResponse
from bcra_rag.ui.config import (
    CANNED_PROMPTS,
    L1_ACCORDION_OPEN_DEFAULT,
    LAYOUT_HELP,
    LAYOUT_STAFF,
    LAYOUT_USER,
    abstain_visible,
    append_messages,
    apply_layout,
    banner_markdown,
    citation_card_markdown,
    citation_cards,
    inspector_payload,
    is_sample_l1,
    l1_markdown,
    layout_updates,
    load_l1,
    title_markdown,
    topbar_markdown,
    trust_markdown,
    trust_payload,
)
from bcra_rag.ui.gradio_app import build_blocks, mount_ui
from bcra_rag.ui.theme import observatory_css_path, observatory_head, observatory_theme
from tests.chat_fixtures import LAST_REFRESH, TO_AS_OF, make_client, seed_ready


def test_observatory_css_tokens() -> None:
    css = observatory_css_path().read_text(encoding="utf-8")
    assert "#04111d" in css
    assert "#72d6cb" in css
    assert "28px" in css
    assert "color-scheme: dark" in css


def test_observatory_theme_helpers() -> None:
    path = observatory_css_path()
    assert path.name == "observatory.css"
    assert path.is_file()
    head = observatory_head()
    assert 'name="theme-color"' in head
    assert "#04111d" in head
    theme = observatory_theme()
    assert theme is not None


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


def test_append_messages_accepts_none_history() -> None:
    rows = append_messages(None, "hola", "respuesta")
    assert rows == [
        {"role": "user", "content": "hola"},
        {"role": "assistant", "content": "respuesta"},
    ]
    again = append_messages(rows, "y ese punto?", "otra")
    assert len(again) == 4


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
    assert TO_AS_OF not in title
    assert LAST_REFRESH not in title
    assert "A8464" not in title
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
    empty = load_l1(tmp_path / "missing.json")
    assert is_sample_l1(empty)


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
    assert "warn" in trust_markdown([{"rule": "x", "verdict": "warn", "detail": ""}])
    assert "block" in trust_markdown([{"rule": "y", "verdict": "block", "detail": ""}])
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
    blocks = build_blocks(
        settings=settings,
        index=index,
        llm=llm,
        sessions=InMemorySessionStore(),
        limiter=RateLimiter(max_requests=20, window_s=60),
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
        "observatory-freeze",
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
    help_box = _widget_by_elem_id(blocks, "layout-toggle-help")
    assert freeze is not None and getattr(freeze, "visible", True) is True
    assert side is not None and getattr(side, "visible", True) is True
    assert help_box is not None
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
    assert getattr(vista, "value", None) == LAYOUT_STAFF
    css = observatory_css_path().read_text(encoding="utf-8")
    assert "#layout-toggle" in css
    assert "#layout-toggle-help" in css


def test_layout_toggle_visibility() -> None:
    hide_freeze, hide_side = layout_updates(False)
    show_freeze, show_side = layout_updates(True)
    assert _update_visible(hide_freeze) is False
    assert _update_visible(hide_side) is False
    assert _update_visible(show_freeze) is True
    assert _update_visible(show_side) is True
    user = apply_layout(LAYOUT_USER)
    staff = apply_layout(LAYOUT_STAFF)
    assert len(user) == 2
    assert len(staff) == 2
    assert _update_visible(user[0]) is False
    assert _update_visible(user[1]) is False
    assert _update_visible(staff[0]) is True
    assert _update_visible(staff[1]) is True
    assert LAYOUT_STAFF in LAYOUT_HELP
    assert LAYOUT_USER in LAYOUT_HELP
    assert "inspector de citas" in LAYOUT_HELP
    assert "Enviar" in LAYOUT_HELP


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
