"""Dump freeze wording shared by the answer path, the freeze-honesty rail and the UI."""

from __future__ import annotations

UNKNOWN = "desconocido"


def dump_date(last_refresh: str | None) -> str:
    if not last_refresh:
        return UNKNOWN
    if len(last_refresh) >= 10 and last_refresh[4] == "-" and last_refresh[7] == "-":
        return last_refresh[:10]
    return last_refresh


def freeze_footer(last_refresh: str | None, to_as_of: str | None) -> str:
    """Spanish freeze sentence. A missing date stays masculine so names_freeze still matches."""
    has_date = bool(last_refresh)
    has_hito = bool(to_as_of)
    if has_date and has_hito:
        return (
            f"Según el extracto del {dump_date(last_refresh)} "
            f"(texto ordenado al {to_as_of})."
        )
    if has_date:
        return (
            f"Según el extracto del {dump_date(last_refresh)} "
            "(texto ordenado a un dato desconocido)."
        )
    if has_hito:
        return (
            "Según el extracto de un día desconocido "
            f"(texto ordenado al {to_as_of})."
        )
    return (
        "Según el extracto de un día desconocido "
        "(texto ordenado a un dato desconocido)."
    )


def names_freeze(answer: str, last_refresh: str | None, to_as_of: str | None) -> bool:
    refresh = last_refresh or UNKNOWN
    as_of = to_as_of or UNKNOWN
    has_refresh = refresh in answer or dump_date(last_refresh) in answer
    return has_refresh and as_of in answer
