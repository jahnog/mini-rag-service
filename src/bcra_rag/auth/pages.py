from __future__ import annotations

import html

from bcra_rag.ui.theme import (
    OG_IMAGE_HREF,
    PAGE_KICKER,
    PAGE_SUBTITLE,
    PAGE_TITLE,
    PORTFOLIO_URL,
    SOURCE_URL,
)

LINK_FAIL_COPY = "Este enlace no es válido o venció."
WEBLAB_CSS_HREF = "/weblab.css"


def confirm_page(email: str) -> str:
    safe = html.escape(email, quote=True)
    return _shell(
        "Iniciar sesión",
        '<section class="wl-panel">'
        '<p class="wl-kicker">Ingreso</p>'
        '<h2 class="wl-title">Confirmá tu ingreso</h2>'
        f'<p class="wl-subtitle">Vas a entrar como <strong>{safe}</strong>.</p>'
        '<form method="post" action="/auth/link">'
        '<div class="wl-actions">'
        f'<button class="wl-btn wl-btn-primary" type="submit">Iniciar sesión como {safe}</button>'
        '<a class="wl-btn wl-btn-ghost" href="/">Volver</a>'
        "</div>"
        "</form>"
        "</section>",
    )


def fail_page() -> str:
    return _shell(
        "Enlace no válido",
        '<section class="wl-panel">'
        '<p class="wl-kicker">Ingreso</p>'
        f'<h2 class="wl-title">{html.escape(LINK_FAIL_COPY, quote=True)}</h2>'
        '<p class="wl-subtitle">Pedí un código nuevo desde el asistente.</p>'
        '<div class="wl-actions">'
        '<a class="wl-btn wl-btn-primary" href="/">Volver al asistente</a>'
        "</div>"
        "</section>",
    )


def _shell(page: str, body: str) -> str:
    """Family page: the vendored template, the topbar, one narrow card, the
    footer. No inline styles, so the CSP can stay strict."""
    title = f"{html.escape(page, quote=True)} · {html.escape(PAGE_TITLE, quote=True)}"
    kicker = html.escape(PAGE_KICKER, quote=True)
    name = html.escape(PAGE_TITLE, quote=True)
    description = html.escape(PAGE_SUBTITLE, quote=True)
    return f"""<!DOCTYPE html>
<html lang="es" class="wl-page">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
  <meta name="theme-color" content="#050821">
  <title>{title}</title>
  <meta name="description" content="{description}">
  <meta property="og:title" content="{title}">
  <meta property="og:description" content="{description}">
  <meta property="og:image" content="{OG_IMAGE_HREF}">
  <link rel="icon" href="/favicon.ico" sizes="48x48">
  <link rel="icon" href="/favicon.svg" type="image/svg+xml">
  <link rel="apple-touch-icon" href="/apple-touch-icon.png">
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Sora:wght@400;500;600;700&amp;display=swap" rel="stylesheet">
  <link rel="stylesheet" href="{WEBLAB_CSS_HREF}">
</head>
<body>
<div class="wl-shell wl-shell-narrow wl-fill">
  <header class="wl-topbar">
    <div class="wl-brand">
      <p class="wl-kicker">{kicker}</p>
      <h1 class="wl-title">{name}</h1>
    </div>
    <nav class="wl-nav" aria-label="Sitio">
      <a href="{PORTFOLIO_URL}">Portafolio</a>
      <a href="/">Asistente</a>
    </nav>
  </header>
  <main class="wl-main" id="main">
{body}
  </main>
  <footer class="wl-footer">
    <p>Parte del portafolio en <a href="{PORTFOLIO_URL}">jahnog.github.io</a> · <a href="{SOURCE_URL}">Código</a></p>
  </footer>
</div>
</body>
</html>
"""
