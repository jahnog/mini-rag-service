from __future__ import annotations

import html

_PAGE = "#04111d"
_TEXT = "#f4fbff"
_MUTED = "#b6c9d4"
_ACCENT = "#72d6cb"
_BTN_FG = "#03101c"

LINK_FAIL_COPY = "Este enlace no es válido o venció."


def confirm_page(email: str) -> str:
    safe = html.escape(email, quote=True)
    return _shell(
        "<h1>Iniciar sesión</h1>"
        f"<p>Vas a entrar como <strong>{safe}</strong>.</p>"
        '<form method="post" action="/auth/link">'
        f'<button type="submit">Iniciar sesión como {safe}</button>'
        "</form>"
    )


def fail_page() -> str:
    return _shell(
        f"<h1>{html.escape(LINK_FAIL_COPY, quote=True)}</h1>"
        '<p><a href="/">Volver al asistente</a></p>'
    )


def _shell(body: str) -> str:
    return f"""<!DOCTYPE html>
<html lang="es">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>BCRA Mini-RAG</title>
  <style>
    body {{ background:{_PAGE}; color:{_TEXT}; font-family: Sora, "Segoe UI", Arial, sans-serif;
      margin:0; padding:2rem; }}
    h1 {{ font-size:1.4rem; }}
    p {{ color:{_MUTED}; }}
    a {{ color:{_ACCENT}; }}
    button {{ background:{_ACCENT}; color:{_BTN_FG}; border:0; padding:0.7rem 1.1rem;
      font-weight:700; cursor:pointer; }}
    button:focus {{ outline:2px solid {_ACCENT}; outline-offset:3px; }}
  </style>
</head>
<body>
{body}
</body>
</html>
"""
