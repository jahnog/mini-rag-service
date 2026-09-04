from __future__ import annotations

DISCLAIMER_TEXT = (
    "Extracto no oficial. No es el BCRA, no es asesoramiento legal ni de inversión. "
    "Vigencia según last_refresh del dump."
)


def disclaimer_for(last_refresh: str | None) -> str:
    dated = last_refresh or "desconocido"
    return (
        "Extracto no oficial. No es el BCRA, no es asesoramiento legal ni de inversión. "
        f"Fecha de dump last_refresh={dated}."
    )
