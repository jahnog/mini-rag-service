from __future__ import annotations

import html
import re

OTP_SUBJECT = "Tu código de BCRA Mini-RAG"
OTP_CODE_RE = re.compile(r"Tu código de acceso es (\d{6})")

_PAGE = "#04111d"
_CARD = "#081a2b"
_TEXT = "#f4fbff"
_MUTED = "#b6c9d4"
_ACCENT = "#72d6cb"
_BTN_FG = "#03101c"
_BORDER = "#2a4a55"


def otp_code_from_text(text: str) -> str | None:
    match = OTP_CODE_RE.search(text or "")
    return match.group(1) if match else None


def otp_body(code: str, *, ttl_s: int, login_url: str | None = None) -> str:
    minutes = max(1, ttl_s // 60)
    lines = [
        f"Tu código de acceso es {code}.",
        f"Vence en {minutes} minutos.",
    ]
    if login_url:
        lines.append("O abrí este enlace:")
        lines.append(login_url)
    lines.append("Si no lo pediste, ignorá este correo.")
    return "\n".join(lines) + "\n"


def otp_html_body(code: str, *, ttl_s: int, login_url: str | None = None) -> str:
    minutes = max(1, ttl_s // 60)
    safe_code = html.escape(code, quote=True)
    safe_minutes = html.escape(str(minutes), quote=True)
    button = ""
    url_row = ""
    if login_url:
        safe_url = html.escape(login_url, quote=True)
        button = (
            f'<a href="{safe_url}" rel="noopener noreferrer" '
            f'style="display:inline-block;padding:12px 20px;background-color:{_ACCENT};'
            f"color:{_BTN_FG};text-decoration:none;font-weight:700;border-radius:8px;\">"
            "Iniciar sesión</a>"
        )
        url_row = (
            f'<p style="color:{_MUTED};font-size:13px;word-break:break-all;">{safe_url}</p>'
        )
    inner = f"""
<table role="presentation" width="600" cellpadding="0" cellspacing="0" border="0"
  bgcolor="{_CARD}" style="background-color:{_CARD};border:1px solid {_BORDER};">
  <tr>
    <td bgcolor="{_CARD}" style="background-color:{_CARD};color:{_ACCENT};padding:20px 24px 8px;
      font-family:Sora, 'Segoe UI', Arial, sans-serif;font-size:13px;letter-spacing:0.08em;">
      BCRA Mini-RAG
    </td>
  </tr>
  <tr>
    <td bgcolor="{_CARD}" style="background-color:{_CARD};color:{_TEXT};padding:0 24px 12px;
      font-family:Sora, 'Segoe UI', Arial, sans-serif;font-size:22px;font-weight:700;">
      Tu código de acceso
    </td>
  </tr>
  <tr>
    <td bgcolor="{_CARD}" style="background-color:{_CARD};color:{_TEXT};padding:8px 24px 16px;
      font-family:Consolas, 'Courier New', monospace;font-size:28px;letter-spacing:0.35em;">
      Tu código de acceso es {safe_code}
    </td>
  </tr>
  <tr>
    <td bgcolor="{_CARD}" style="background-color:{_CARD};color:{_MUTED};padding:0 24px 16px;
      font-family:Sora, 'Segoe UI', Arial, sans-serif;font-size:14px;">
      Vence en {safe_minutes} minutos.
    </td>
  </tr>
  <tr>
    <td bgcolor="{_CARD}" style="background-color:{_CARD};padding:0 24px 16px;">
      {button}
      {url_row}
    </td>
  </tr>
  <tr>
    <td bgcolor="{_CARD}" style="background-color:{_CARD};color:{_MUTED};padding:0 24px 24px;
      font-family:Sora, 'Segoe UI', Arial, sans-serif;font-size:13px;">
      Si no lo pediste, ignorá este correo.
    </td>
  </tr>
</table>
"""
    return (
        '<!DOCTYPE html><html lang="es"><body '
        f'bgcolor="{_PAGE}" style="background-color:{_PAGE};margin:0;padding:24px;">'
        f"{inner}</body></html>"
    )
