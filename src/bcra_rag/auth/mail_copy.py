from __future__ import annotations

OTP_SUBJECT = "Tu código de BCRA Mini-RAG"


def otp_body(code: str, *, ttl_s: int) -> str:
    minutes = max(1, ttl_s // 60)
    return (
        f"Tu código de acceso es {code}.\n"
        f"Vence en {minutes} minutos.\n"
        "Si no lo pediste, ignorá este correo.\n"
    )
