from __future__ import annotations

from bcra_rag.domain.freeze import dump_date

DISCLAIMER_TEXT = (
    "Extracto no oficial. No es el BCRA, no es asesoramiento legal ni de inversión. "
    "La vigencia es la de la última actualización del extracto."
)


def disclaimer_for(last_refresh: str | None) -> str:
    fecha = dump_date(last_refresh) if last_refresh else "desconocida"
    return (
        "Extracto no oficial. No es el BCRA, no es asesoramiento legal ni de inversión. "
        f"Fecha del extracto: {fecha}."
    )
