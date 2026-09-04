from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import gradio as gr

from bcra_rag.domain.disclaimer import DISCLAIMER_TEXT, disclaimer_for
from bcra_rag.schemas import ChatResponse, HealthResponse

CANNED_PROMPTS: tuple[str, ...] = (
    "Cuál es la regla vigente del tipo de cambio de referencia (A 3500 vs A 8359)?",
    "qué se exige hoy para liquidar el cobro de exportaciones",
    "Sigue vigente la Comunicación A de 2001-2002 sobre el cepo como regla actual?",
    "Qué dice la Comunicación A 9999?",
)

L1_ACCORDION_OPEN_DEFAULT = False

LAYOUT_STAFF = "Staff (IA)"
LAYOUT_USER = "Usuario"
LAYOUT_HELP = (
    "Staff (IA) muestra el inspector de citas, el log de guardrails, "
    "Calidad L1 y las fechas del dump. Usuario deja solo la pregunta, "
    "la respuesta, Enviar, Clear y los ejemplos."
)


def banner_markdown(health: HealthResponse) -> str:
    return (
        "**Extracto no oficial BCRA CAMEX** — no es el BCRA ni asesoramiento legal.\n\n"
        f"to_as_of=`{health.to_as_of}` · last_refresh=`{health.last_refresh}` · "
        f"last A=`{health.last_comm_id}` · n_docs={health.n_docs}"
    )


def title_markdown(health: HealthResponse) -> str:
    del health
    return (
        "*BCRA Mini-RAG · extracto no oficial CAMEX*\n\n"
        "# Preguntá por una cláusula. Recibí cita o silencio.\n\n"
    )


def topbar_markdown(health: HealthResponse) -> str:
    return title_markdown(health) + banner_markdown(health)


def layout_updates(staff: bool) -> tuple[Any, Any]:
    update = gr.update(visible=staff)
    return update, update


def apply_layout(choice: str | None) -> tuple[Any, Any]:
    return layout_updates(choice == LAYOUT_STAFF)


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
    b_docs = data.get("chunking", {}).get("b_documents") or data.get("b_documents") or []
    slices = data.get("slices") or {}
    slice_lines = "\n".join(f"- {key}: {value}" for key, value in slices.items())
    return (
        f"{label}"
        f"Headline **{headline}**: {data.get('citation_id_exact')}\n\n"
        f"hit@5: {data.get('hit_at_5')} · MRR: {data.get('mrr')}\n\n"
        f"A vs B: {data.get('chunking', {})}\n"
        f"Strategy B documents: {', '.join(str(x) for x in b_docs) or '(none)'}\n\n"
        f"Slices:\n{slice_lines or '- (none)'}"
    )


def footer_text(last_refresh: str | None) -> str:
    return disclaimer_for(last_refresh) if last_refresh else DISCLAIMER_TEXT


def append_messages(
    history: list[dict[str, str]] | None,
    user: str,
    assistant: str,
) -> list[dict[str, str]]:
    rows = list(history or [])
    rows.append({"role": "user", "content": user})
    rows.append({"role": "assistant", "content": assistant})
    return rows


def citation_card_markdown(card: dict[str, Any] | None) -> str:
    if not card:
        return ""
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
        {"rule": item.rule, "verdict": item.verdict, "detail": item.detail}
        for item in response.guardrails
    ]


def trust_markdown(rows: list[dict[str, str]] | None) -> str:
    if not rows:
        return ""
    lines: list[str] = []
    for item in rows:
        rule = str(item.get("rule") or "")
        verdict = str(item.get("verdict") or "")
        detail = str(item.get("detail") or "").strip()
        line = f"- `{verdict}` **{rule}**"
        if detail:
            line += f" — {detail}"
        lines.append(line)
    return "\n".join(lines)


def abstain_visible(response: ChatResponse | None) -> bool:
    return bool(response and response.finding.value == "silencio")
