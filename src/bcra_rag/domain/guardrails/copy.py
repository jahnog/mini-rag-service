"""User-facing Spanish copy for blocked turns and the guardrail log."""

from __future__ import annotations

NO_CLAUSE = "No hay una cláusula del extracto CAMEX que responda esto."

RULE_LABELS: dict[str, str] = {
    "length": "longitud",
    "normalize": "normalización",
    "secrets": "secretos",
    "secrets-output": "secretos",
    "no-advice": "sin consejo",
    "no-advice-output": "sin consejo",
    "injection": "inyección",
    "scope": "alcance",
    "chunk-hygiene": "higiene",
    "chunk-injection": "inyección en documentos",
    "context-budget": "límite de contexto",
    "generate": "redacción",
    "retrieve": "búsqueda",
    "cite-or-abstain": "citar o callar",
    "freeze-honesty": "vigencia",
    "prompt-leak": "fuga de instrucciones",
    "unsafe-output": "salida insegura",
    "markdown-sanitize": "marcado",
}

VERDICT_LABELS: dict[str, str] = {
    "pass": "aprobado",
    "warn": "aviso",
    "block": "bloqueo",
    "redact": "modificado",
    "skipped": "omitido",
}

STAGE_LABELS: dict[str, str] = {
    "input": "entrada",
    "retrieve": "búsqueda",
    "generate": "redacción",
    "output": "salida",
}

DETAIL_LABELS: dict[str, str] = {
    "cleared": "sesión borrada",
    "index_not_ready": "el índice no está listo",
    "empty_hits": "sin resultados",
    "retrieve_empty": "la búsqueda quedó vacía",
    "missing_document": "falta el documento",
    "empty_extract": "el extracto está vacío",
    "missing_xref": "falta la referencia",
    "llm_timeout": "el modelo tardó demasiado",
    "llm_bad_json": "el modelo devolvió un texto ilegible",
    "llm_unavailable": "no hay modelo disponible",
    "retry_no_thinking": "reintento sin razonamiento",
}

BLOCKED_COPY: dict[str, str] = {
    "length": "No puedo responder: la pregunta es demasiado larga.",
    "secrets": "No puedo responder: la pregunta contiene una clave o un secreto.",
    "no-advice": "No puedo responder: no doy consejos de inversión ni de cumplimiento.",
    "injection": "No puedo responder: la pregunta intenta cambiar mis instrucciones.",
    "scope": (
        "No puedo responder: la pregunta no es sobre la normativa cambiaria CAMEX del BCRA."
    ),
    "no-advice-output": "No puedo responder: la respuesta contendría un consejo.",
    "secrets-output": "No puedo responder: la respuesta contendría un secreto.",
    "prompt-leak": "No puedo responder: la respuesta expondría instrucciones internas.",
    "chunk-injection": (
        "No puedo responder: los documentos recuperados contienen instrucciones sospechosas."
    ),
}


def blocked_copy(rule: str) -> str:
    return BLOCKED_COPY.get(rule, f"No puedo responder ({rule_label(rule)}).")


def rule_label(rule: str) -> str:
    return RULE_LABELS.get(rule, rule)


def verdict_label(verdict: str) -> str:
    return VERDICT_LABELS.get(verdict, verdict)


def stage_label(stage: str) -> str:
    return STAGE_LABELS.get(stage, stage)


def detail_label(detail: str) -> str:
    """Spanish wording for a guardrail log line. Machine codes stay in abstain_reason."""
    text = (detail or "").strip()
    known = DETAIL_LABELS.get(text)
    if known is not None:
        return known
    prefix = "blocked by "
    if text.startswith(prefix):
        return f"bloqueado por {rule_label(text[len(prefix) :])}"
    if text == "llm called":
        return "modelo consultado"
    if text.startswith("llm called ("):
        inner = text.removeprefix("llm called (").removesuffix(")")
        return f"modelo consultado ({detail_label(inner)})"
    return text
