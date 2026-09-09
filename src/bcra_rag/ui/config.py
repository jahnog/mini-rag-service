from __future__ import annotations

import html
import json
import re
from pathlib import Path
from typing import Any

import gradio as gr
from fastapi import HTTPException

from bcra_rag.domain.disclaimer import DISCLAIMER_TEXT
from bcra_rag.schemas import ChatResponse, HealthResponse

CANNED_PROMPTS: tuple[str, ...] = (
    "Cuál es la regla vigente del tipo de cambio de referencia (A 3500 vs A 8359)?",
    "Qué se exige hoy para liquidar el cobro de exportaciones",
    "Sigue vigente la Comunicación A de 2001-2002 sobre el cepo como regla actual?",
    "Qué dice la Comunicación A 9999?",
)

L1_ACCORDION_OPEN_DEFAULT = False
EMPTY_CITATION_CARD = "Todavía no hay citas en esta consulta."
EMPTY_TRUST = '<p class="obs-empty">Sin guardrails todavía.</p>'
_TRUST_VERDICTS = frozenset({"pass", "warn", "block", "redact", "skipped"})

LAYOUT_STAFF = "Staff (IA)"
LAYOUT_USER = "Usuario"
LAYOUT_STAFF_CLASS = "layout-staff"
LAYOUT_USER_CLASS = "layout-user"
LAYOUT_HELP = (
    "Staff (IA) muestra el razonamiento, el inspector de citas, "
    "el log de guardrails, Calidad L1 y las fechas del dump.\n\n"
    "Usuario deja solo la pregunta, la respuesta, Enviar, Clear y los ejemplos."
)
AUTH_EMAIL_LABEL = "Correo"
AUTH_SEND = "Enviar código"
AUTH_CODE_LABEL = "Código"
AUTH_VERIFY = "Verificar"
AUTH_LOGOUT = "Cerrar sesión"
AUTH_STATUS_GENERIC = "Si el correo está habilitado, vas a recibir un código."
AUTH_NOTICE = "Tenés que ingresar con tu email."


def banner_markdown(health: HealthResponse) -> str:
    return (
        "**Extracto no oficial BCRA CAMEX** — no es el BCRA ni asesoramiento legal.\n\n"
        f"to_as_of=`{health.to_as_of}` · last_refresh=`{health.last_refresh}` · "
        f"last A=`{health.last_comm_id}` · n_docs={health.n_docs}"
    )


def title_markdown(health: HealthResponse) -> str:
    del health
    return (
        "BCRA Mini-RAG · extracto no oficial CAMEX\n\n"
        "# Preguntá por una cláusula. Recibí cita o silencio."
    )


def dump_date(last_refresh: str | None) -> str:
    if not last_refresh:
        return "desconocido"
    if len(last_refresh) >= 10 and last_refresh[4] == "-" and last_refresh[7] == "-":
        return last_refresh[:10]
    return last_refresh


def freeze_chips_html(health: HealthResponse) -> str:
    iso = html.escape(health.last_refresh or "")
    date = html.escape(dump_date(health.last_refresh))
    to_as_of = html.escape(str(health.to_as_of or "—"))
    last_a = html.escape(str(health.last_comm_id or "—"))
    n_docs = html.escape(str(health.n_docs))
    return (
        '<div class="obs-chips">'
        f'<span class="obs-chip">TO {to_as_of}</span>'
        f'<span class="obs-chip" title="{iso}">Dump {date}</span>'
        f'<span class="obs-chip">Última A {last_a}</span>'
        f'<span class="obs-chip">{n_docs} docs</span>'
        "</div>"
    )


def topbar_markdown(health: HealthResponse) -> str:
    return title_markdown(health) + banner_markdown(health)


def layout_updates(staff: bool) -> tuple[Any, Any]:
    update = gr.update(visible=staff)
    return update, update


def layout_shell_classes(staff: bool) -> list[str]:
    return [LAYOUT_STAFF_CLASS if staff else LAYOUT_USER_CLASS]


def apply_clear_result(
    history: list[ChatRow] | None,
    session_id: str | None,
    error: HTTPException | None = None,
) -> tuple[list[ChatRow], str | None]:
    if error is not None:
        notice = http_turn_notice(error.status_code, str(error.detail))
        rows = list(history or [])
        rows.append({"role": "assistant", "content": notice})
        return rows, session_id
    return [], None


def http_turn_notice(status: int, detail: str | None = None) -> str:
    if status == 401:
        if detail == "authentication required":
            return AUTH_NOTICE
        return "Se requiere DEMO_API_KEY."
    if status == 429:
        return "Demasiadas solicitudes."
    return "Solicitud rechazada."


def thinking_for_staff(thinking: str | None, *, staff: bool) -> str | None:
    if not staff:
        return None
    return (thinking or "").strip() or None


def apply_layout(
    choice: str | None, authenticated: bool = False
) -> tuple[Any, Any, Any]:
    staff = bool(authenticated) and choice == LAYOUT_STAFF
    freeze, side = layout_updates(staff)
    shell = gr.update(elem_classes=layout_shell_classes(staff))
    return freeze, side, shell


def auth_chrome(authenticated: bool, email: str | None = None) -> tuple[Any, Any, Any]:
    who = email or ""
    return (
        gr.update(visible=not authenticated),
        gr.update(visible=authenticated),
        gr.update(value=who),
    )


def load_l1(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {
            "unpublished": True,
            "sample": True,
            "headline_metric": "citation_id_exact",
            "citation_id_exact": None,
            "hit_at_5": None,
            "mrr": None,
        }
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        return {"unpublished": True, "sample": True}
    return raw


def is_sample_l1(data: dict[str, Any]) -> bool:
    return bool(data.get("unpublished") or data.get("sample"))


def l1_markdown(data: dict[str, Any]) -> str:
    label = ""
    if is_sample_l1(data):
        label = (
            "**Números unpublished/sample** — no son una corrida de operador.\n\n"
        )
    headline = data.get("headline_metric", "citation_id_exact")
    raw_chunking = data.get("chunking")
    chunking: dict[str, Any] = raw_chunking if isinstance(raw_chunking, dict) else {}
    a_score = chunking.get("A", data.get("A", "—"))
    b_score = chunking.get("B", data.get("B", "—"))
    b_docs = chunking.get("b_documents") or data.get("b_documents") or []
    slices = data.get("slices") or {}
    slice_lines = "\n".join(f"- {key}: {value}" for key, value in slices.items())
    raw_retrieval = data.get("retrieval")
    raw_generation = data.get("generation")
    retrieval: dict[str, Any] = raw_retrieval if isinstance(raw_retrieval, dict) else {}
    generation: dict[str, Any] = raw_generation if isinstance(raw_generation, dict) else {}
    retrieval_block = _suite_markdown("Retrieval", retrieval)
    generation_block = _suite_markdown("Generation", generation)
    citation_shown = _skipped_or_value(
        data.get("citation_id_exact"), bool(generation.get("skipped"))
    )
    hit_shown = _skipped_or_value(data.get("hit_at_5"), bool(retrieval.get("skipped")))
    mrr_shown = _skipped_or_value(data.get("mrr"), bool(retrieval.get("skipped")))
    return (
        f"{label}"
        f"Headline **{headline}**: {citation_shown}\n\n"
        f"hit@5: {hit_shown} · MRR: {mrr_shown}\n\n"
        f"{retrieval_block}\n\n"
        f"{generation_block}\n\n"
        f"A vs B: A {a_score} · B {b_score}\n\n"
        f"Strategy B documents: {', '.join(str(x) for x in b_docs) or '(none)'}\n\n"
        f"Slices:\n{slice_lines or '- (none)'}"
    )


def _skipped_or_value(value: object, skipped: bool) -> str:
    if skipped or value is None:
        return "skipped"
    return str(value)


def _suite_markdown(title: str, block: dict[str, Any]) -> str:
    if not block:
        return f"## {title}\n\n(not present)"
    if block.get("skipped"):
        reason = block.get("skip_reason") or "skipped"
        return f"## {title}\n\nskipped ({reason})"
    lines = [f"## {title}", ""]
    skip = {"skipped", "skip_reason"}
    for key, value in block.items():
        if key in skip:
            continue
        lines.append(f"- {key}: {value}")
    return "\n".join(lines)


def footer_text(last_refresh: str | None) -> str:
    if not last_refresh:
        return DISCLAIMER_TEXT
    return (
        "Extracto no oficial. No es el BCRA, no es asesoramiento legal ni de inversión. "
        f"Fecha de dump {dump_date(last_refresh)}."
    )


THOUGHT_PENDING_TITLE = "Pensando…"
ChatRow = dict[str, Any]
_ATX_HEADING = re.compile(r"(?m)^(#{1,6})(?=\s|$)")
_THOUGHT_BREAK = frozenset(" \t\n\r.,;:!?…)]}\"'»")
THOUGHT_PUBLISH_S = 0.12


def thought_markdown(text: str) -> str:
    """Keep CoT at body size: streaming `#` / `##` must not become Markdown headings."""
    return _ATX_HEADING.sub(lambda match: "\\" + match.group(1), text)


def thought_publish_ready(text: str) -> bool:
    """True when the trace ends on a word/punctuation break (not mid-token)."""
    if not text:
        return False
    return text[-1] in _THOUGHT_BREAK


def thought_message(
    content: str,
    *,
    title: str,
    status: str | None = None,
    duration: float | None = None,
) -> ChatRow:
    metadata: dict[str, Any] = {"title": title}
    if status is not None:
        metadata["status"] = status
    if duration is not None:
        metadata["duration"] = duration
    return {
        "role": "assistant",
        "content": thought_markdown(content),
        "metadata": metadata,
    }


def done_thought_title(duration: float | None) -> str:
    if duration is None:
        return "Pensó"
    if duration >= 1:
        return f"Pensó {int(round(duration))}s"
    return f"Pensó {duration:.1f}s"


def _copy_row(row: ChatRow) -> ChatRow:
    copied = dict(row)
    meta = copied.get("metadata")
    if isinstance(meta, dict):
        copied["metadata"] = dict(meta)
    return copied


def collapse_prior_thoughts(history: list[ChatRow] | None) -> list[ChatRow]:
    rows: list[ChatRow] = []
    for row in history or []:
        copied = _copy_row(row)
        meta = copied.get("metadata")
        if isinstance(meta, dict) and meta.get("title"):
            copied["metadata"] = {**meta, "status": "done"}
        rows.append(copied)
    return rows


def append_pending(
    history: list[ChatRow] | None,
    user: str,
    thinking: str = "",
) -> list[ChatRow]:
    rows = collapse_prior_thoughts(history)
    rows.append({"role": "user", "content": user})
    rows.append(
        thought_message(
            thinking, title=THOUGHT_PENDING_TITLE, status="pending"
        )
    )
    return rows


def append_messages(
    history: list[ChatRow] | None,
    user: str,
    assistant: str,
    *,
    thinking: str | None = None,
    duration: float | None = None,
) -> list[ChatRow]:
    rows = collapse_prior_thoughts(history)
    rows.append({"role": "user", "content": user})
    trace = (thinking or "").strip()
    if trace:
        rows.append(
            thought_message(
                trace,
                title=done_thought_title(duration),
                duration=duration,
            )
        )
    rows.append({"role": "assistant", "content": assistant})
    return rows


def citation_card_markdown(card: dict[str, Any] | None) -> str:
    if not card:
        return EMPTY_CITATION_CARD
    punto = card.get("punto") or "—"
    fecha = card.get("fecha") or "—"
    url = card.get("url") or ""
    snippet = card.get("snippet") or ""
    copy_id = card.get("copy_id") or card.get("id") or ""
    return (
        f"**{card.get('id')}** · fecha {fecha} · punto {punto}\n\n"
        f"{snippet}\n\n"
        f"copy-id `{copy_id}`\n\n"
        f"{url}"
    )


def citation_cards(response: ChatResponse | None) -> list[dict[str, Any]]:
    if response is None:
        return []
    return [
        {
            "id": item.id,
            "fecha": item.fecha,
            "punto": item.punto,
            "snippet": item.snippet,
            "copy_id": item.id,
            "url": item.url,
        }
        for item in response.citations
    ]


def inspector_payload(
    response: ChatResponse | None,
    selected_id: str | None = None,
) -> dict[str, Any]:
    cards = citation_cards(response)
    if not cards:
        return {}
    if selected_id:
        for card in cards:
            if card["id"] == selected_id:
                return card
    return cards[0]


def trust_payload(response: ChatResponse | None) -> list[dict[str, str]]:
    if response is None:
        return []
    return [
        {
            "rule": item.rule,
            "verdict": item.verdict,
            "detail": item.detail,
            "stage": item.stage,
            "enforced": "true" if item.enforced else "false",
            "would_block": "true" if item.would_block else "false",
        }
        for item in response.guardrails
    ]


def trust_markdown(rows: list[dict[str, str]] | None) -> str:
    if not rows:
        return EMPTY_TRUST
    parts: list[str] = ['<div class="obs-trust">']
    current = ""
    for item in rows:
        stage = str(item.get("stage") or "")
        if stage and stage != current:
            current = stage
            parts.append(f'<div class="obs-trust-stage">{html.escape(stage)}</div>')
        rule = html.escape(str(item.get("rule") or ""))
        verdict = html.escape(str(item.get("verdict") or ""))
        detail = html.escape(str(item.get("detail") or "").strip())
        cls = verdict if verdict in _TRUST_VERDICTS else "pass"
        row = (
            '<div class="obs-trust-row">'
            f'<span class="obs-chip {cls}">{verdict} {rule}</span>'
        )
        if detail:
            row += f'<span class="obs-trust-detail">{detail}</span>'
        if item.get("enforced") == "false":
            row += '<span class="obs-trust-detail">not enforced</span>'
        if item.get("would_block") == "true":
            row += '<span class="obs-trust-detail">would-block</span>'
        row += "</div>"
        parts.append(row)
    parts.append("</div>")
    return "".join(parts)


def abstain_visible(response: ChatResponse | None) -> bool:
    return bool(response and response.finding.value == "silencio")
