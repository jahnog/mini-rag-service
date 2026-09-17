"""User-facing Spanish copy for blocked turns, keyed by rule id."""

from __future__ import annotations

BLOCKED_COPY: dict[str, str] = {
    "length": "No puedo responder: la pregunta es demasiado larga.",
    "secrets": "No puedo responder: la pregunta contiene una clave o secreto.",
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
    return BLOCKED_COPY.get(rule, f"No puedo responder ({rule}).")
