from __future__ import annotations

import html
import re
from typing import Any

import gradio as gr
from fastapi import HTTPException

from bcra_rag.domain.disclaimer import DISCLAIMER_TEXT
from bcra_rag.domain.freeze import dump_date as dump_date
from bcra_rag.domain.guardrails.copy import rule_label, stage_label, verdict_label
from bcra_rag.domain.l1_results import L1_FILENAME as L1_FILENAME
from bcra_rag.domain.l1_results import is_sample_l1 as is_sample_l1
from bcra_rag.domain.l1_results import load_l1 as load_l1
from bcra_rag.schemas import ChatResponse, HealthResponse
from bcra_rag.settings import Settings

CANNED_PROMPTS: tuple[str, ...] = (
    "¿Cuál es la regla vigente del tipo de cambio de referencia (A 3500 vs A 8359)?",
    "¿Qué se exige hoy para liquidar el cobro de exportaciones?",
    "¿Sigue vigente la Comunicación A de 2001-2002 sobre el cepo como regla actual?",
    "¿Qué dice la Comunicación A 9999?",
)

L1_ACCORDION_OPEN_DEFAULT = False
EMPTY_CITATION_CARD = "Todavía no hay citas en esta consulta."
EMPTY_TRUST = '<p class="obs-empty">Sin controles todavía.</p>'
PENDING_CITATION_CARD = "Buscando citas…"
PENDING_TRUST = '<p class="obs-empty">Controles en curso…</p>'
TURN_FAILED_NOTICE = "Error interno al responder. Probá de nuevo."
CITATIONS_KICKER = "Citas"
GUARDRAILS_KICKER = "Controles"
_TRUST_VERDICTS = frozenset({"pass", "warn", "block", "redact", "skipped"})

LAYOUT_STAFF = "Operador (IA)"
LAYOUT_USER = "Usuario"
LAYOUT_STAFF_CLASS = "layout-staff"
LAYOUT_USER_CLASS = "layout-user"
LAYOUT_HELP = (
    "Operador (IA) muestra el inspector de citas, el registro de controles, "
    "Calidad L1 y las fechas del extracto.\n\n"
    "Usuario deja solo la pregunta, la respuesta, Enviar, Limpiar y los ejemplos."
)
AUTH_KICKER = "Ingreso"
CHAT_KICKER = "Consulta"
EXAMPLES_KICKER = "Ejemplos"
AUTH_EMAIL_LABEL = "Correo"
AUTH_SEND = "Enviar código"
AUTH_CODE_LABEL = "Código"
AUTH_VERIFY = "Verificar"
AUTH_LOGOUT = "Cerrar sesión"
AUTH_CLEAR = "Limpiar"
AUTH_STATUS_GENERIC = "Si el correo está habilitado, vas a recibir un código."
AUTH_STATUS_SENDING = "Enviando…"


def auth_status_smtp_ok(ttl_s: int) -> str:
    minutes = max(1, round(ttl_s / 60))
    unit = "minuto" if minutes == 1 else "minutos"
    return (
        "Listo. Si pediste un código hace menos de "
        f"{minutes} {unit}, usá ese; si no, revisá tu correo."
    )


AUTH_STATUS_SMTP_OK = auth_status_smtp_ok(300)
AUTH_STATUS_SMTP_FAIL = "No se pudo enviar el código"
AUTH_STATUS_SMTP_PROBLEM = "Hubo un problema al enviar el código."
AUTH_STATUS_FLASH_MS = 2000
AUTH_NOTICE = "Tenés que ingresar con tu correo."


def freeze_chips_html(health: HealthResponse) -> str:
    iso = html.escape(health.last_refresh or "")
    date = html.escape(dump_date(health.last_refresh))
    to_as_of = html.escape(str(health.to_as_of or "—"))
    last_a = html.escape(str(health.last_comm_id or "—"))
    n_docs = html.escape(str(health.n_docs))
    return (
        '<div class="obs-chips">'
        f'<span class="obs-chip" title="Texto ordenado según {to_as_of}">TO {to_as_of}</span>'
        f'<span class="obs-chip" title="Última actualización del corpus: {iso}">'
        f"Extracto {date}</span>"
        f'<span class="obs-chip" title="Última Comunicación A ingerida">Última A {last_a}</span>'
        f'<span class="obs-chip" title="Documentos en el índice">{n_docs} documentos</span>'
        "</div>"
    )


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
        return "Se requiere la clave de demostración."
    if status == 429:
        return "Demasiados intentos. Probá más tarde."
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


def l1_markdown(data: dict[str, Any]) -> str:
    """Reprint the last offline L1 file. The headline is citation-id exact match.

    ``omitido`` means that suite or the judge did not run, not that the score
    is zero. Chunking A and B are how many chunks each splitter produces for
    texto ordenado, not a quality score.
    """
    label = ""
    if is_sample_l1(data):
        label = (
            "**Números de muestra, no publicados** — no son una corrida de operador.\n\n"
        )
    headline = _metric_label(str(data.get("headline_metric", "citation_id_exact")))
    raw_chunking = data.get("chunking")
    chunking: dict[str, Any] = raw_chunking if isinstance(raw_chunking, dict) else {}
    a_score = chunking.get("A", data.get("A", "—"))
    b_score = chunking.get("B", data.get("B", "—"))
    b_docs = chunking.get("b_documents") or data.get("b_documents") or []
    slices = data.get("slices") or {}
    slice_lines = "\n".join(
        f"- {_slice_label(str(key))}: {value}" for key, value in slices.items()
    )
    raw_retrieval = data.get("retrieval")
    raw_generation = data.get("generation")
    retrieval: dict[str, Any] = raw_retrieval if isinstance(raw_retrieval, dict) else {}
    generation: dict[str, Any] = raw_generation if isinstance(raw_generation, dict) else {}
    retrieval_block = _suite_markdown("Recuperación", retrieval)
    generation_block = _suite_markdown("Generación", generation)
    judge_line = _judge_markdown(data.get("judge"))
    citation_shown = _skipped_or_value(
        data.get("citation_id_exact"), bool(generation.get("skipped"))
    )
    hit_shown = _skipped_or_value(data.get("hit_at_5"), bool(retrieval.get("skipped")))
    mrr_shown = _skipped_or_value(data.get("mrr"), bool(retrieval.get("skipped")))
    return (
        f"{label}"
        f"Métrica principal **{headline}**: {citation_shown}\n\n"
        f"acierto@5: {hit_shown} · MRR: {mrr_shown}\n\n"
        f"{retrieval_block}\n\n"
        f"{generation_block}\n\n"
        f"{judge_line + chr(10) + chr(10) if judge_line else ''}"
        f"Fragmentos A vs B: A {a_score} · B {b_score}\n\n"
        f"Documentos de la estrategia B: {', '.join(str(x) for x in b_docs) or '(ninguno)'}\n\n"
        f"Grupos:\n{slice_lines or '- (ninguno)'}"
    )


def _skipped_or_value(value: object, skipped: bool) -> str:
    if skipped or value is None:
        return "omitido"
    if isinstance(value, float):
        return f"{value:.3f}"
    return str(value)


_LATENCY_KEYS = frozenset({"latency_ms_p50", "latency_ms_p95"})
_METRIC_LABELS = {
    "citation_id_exact": "coincidencia de cita",
    "hit_at_5": "acierto@5",
    "precision_at_5": "precisión@5",
    "mrr": "MRR",
    "ndcg_at_5": "NDCG@5",
    "latency_ms_p50": "latencia p50",
    "latency_ms_p95": "latencia p95",
    "n_context_recall": "juicios de exhaustividad",
    "citation_punto_exact": "punto exacto",
    "citation_snippet_grounded": "fragmento anclado",
    "finding_exact": "hallazgo exacto",
    "context_source": "fuente del contexto",
    "faithfulness": "fidelidad",
    "answer_relevancy": "relevancia",
    "context_precision": "precisión de contexto",
    "context_recall": "exhaustividad del contexto",
}
_SLICE_LABELS = {
    "cross-ref": "referencia cruzada",
    "english": "inglés",
    "post-to": "posterior al texto ordenado",
    "superseded": "reemplazada",
}
_SKIP_LABELS = {
    "missing_extra": "falta la dependencia del juez",
    "not_requested": "no se pidió",
    "no_llm": "sin modelo",
    "no_judge": "sin juez",
    "deterministic_only": "solo métricas deterministas",
    "retrieved_context_requires_retrieval": "hace falta la búsqueda",
}
_CONTEXT_SOURCES = {"oracle": "oráculo", "retrieved": "recuperado"}


def _metric_label(key: str) -> str:
    return _METRIC_LABELS.get(key, key)


def _slice_label(key: str) -> str:
    return _SLICE_LABELS.get(key, key)


def _skip_label(reason: str) -> str:
    return _SKIP_LABELS.get(reason, reason)


def _fmt_metric(key: str, value: object) -> str:
    if value is None:
        return "omitido"
    if key == "context_source" and isinstance(value, str):
        return _CONTEXT_SOURCES.get(value, value)
    if isinstance(value, bool):
        return "sí" if value else "no"
    if key in _LATENCY_KEYS and isinstance(value, int | float):
        return f"{int(round(value))} ms"
    if isinstance(value, float):
        return f"{value:.3f}"
    return str(value)


def _judge_markdown(raw: object) -> str:
    if not isinstance(raw, dict):
        return ""
    model = str(raw.get("model") or "—")
    if raw.get("skipped"):
        reason = _skip_label(str(raw.get("skip_reason") or "omitido"))
        return f"Juez: {model} · omitido ({reason})"
    return f"Juez: {model} · {int(raw.get('calls') or 0)} llamadas"


def _suite_markdown(title: str, block: dict[str, Any]) -> str:
    """One retrieval or generation block from the L1 file, including its skip reason."""
    if not block:
        return f"## {title}\n\n(sin datos)"
    if block.get("skipped"):
        reason = _skip_label(str(block.get("skip_reason") or "omitido"))
        return f"## {title}\n\nomitido ({reason})"
    n = block.get("n")
    heading = f"## {title} (n={n})" if n is not None else f"## {title}"
    lines = [heading, ""]
    skip = {"skipped", "skip_reason", "n"}
    for key, value in block.items():
        if key in skip:
            continue
        lines.append(f"- {_metric_label(str(key))}: {_fmt_metric(key, value)}")
    return "\n".join(lines)


def footer_text(last_refresh: str | None) -> str:
    if not last_refresh:
        return DISCLAIMER_TEXT
    return (
        "Extracto no oficial. No es el BCRA, no es asesoramiento legal ni de inversión. "
        f"Fecha del extracto: {dump_date(last_refresh)}."
    )


THOUGHT_PENDING_TITLE = "Pensando…"
ChatRow = dict[str, Any]
_ATX_HEADING = re.compile(r"(?m)^(#{1,6})(?=\s|$)")
_THOUGHT_BREAK = frozenset(" \t\n\r.,;:!?…)]}\"'»")
THOUGHT_PUBLISH_S = 0.5
# retrieve = search, generate = model draft, verify = the output rails.
PHASE_COPY = {
    "retrieve": "Buscando en el extracto…",
    "generate": "Redactando respuesta…",
    "verify": "Verificando citas…",
}


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
    *,
    title: str = THOUGHT_PENDING_TITLE,
) -> list[ChatRow]:
    rows = collapse_prior_thoughts(history)
    rows.append({"role": "user", "content": user})
    rows.append(thought_message(thinking, title=title, status="pending"))
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
    """One citation: a dump document id, an optional punto, and a retrieved quote.

    The id is a Comunicación "A" number or texto ordenado, not a chunk id.
    """
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
        f"identificador `{copy_id}`\n\n"
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
    """One row per guardrail. An unenforced block is stored as pass; see would_block.

    Verdicts follow GuardrailPipeline: enforcement off rewrites block to pass
    and still sets would_block, so the panel shows both.
    """
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
    """Render the guardrail log, including would_block next to a rewritten pass."""
    if not rows:
        return EMPTY_TRUST
    parts: list[str] = ['<div class="obs-trust">']
    current = ""
    for item in rows:
        stage = str(item.get("stage") or "")
        if stage and stage != current:
            current = stage
            parts.append(
                f'<div class="obs-trust-stage">{html.escape(stage_label(stage))}</div>'
            )
        rule = str(item.get("rule") or "")
        verdict = str(item.get("verdict") or "")
        detail = html.escape(str(item.get("detail") or "").strip())
        cls = verdict if verdict in _TRUST_VERDICTS else "skipped"
        shown = html.escape(f"{verdict_label(verdict)} {rule_label(rule)}")
        row = (
            '<div class="obs-trust-row">'
            f'<span class="obs-chip {cls}">{shown}</span>'
        )
        if detail:
            row += f'<span class="obs-trust-detail">{detail}</span>'
        if item.get("enforced") == "false":
            row += '<span class="obs-trust-detail">no aplicado</span>'
        if item.get("would_block") == "true":
            row += '<span class="obs-trust-detail">bloquearía</span>'
        row += "</div>"
        parts.append(row)
    parts.append("</div>")
    return "".join(parts)


def abstain_visible(response: ChatResponse | None) -> bool:
    """True when the finding is silencio: a deliberate abstention, not an exception."""
    return bool(response and response.finding.value == "silencio")


def thinking_for_layout(staff: bool, settings: Settings) -> bool | None:
    """None keeps LLM_ENABLE_THINKING; False turns thinking off for a Usuario turn."""
    if staff or settings.llm_thinking_user_layout:
        return None
    return False
