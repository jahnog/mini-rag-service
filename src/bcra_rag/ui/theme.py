from __future__ import annotations

import html as html_lib
import json
import re
from pathlib import Path
from urllib.parse import urlparse, urlunparse

import gradio as gr
from gradio.themes import Base, GoogleFont

WEBLAB_CSS_PATH = Path(__file__).with_name("weblab.css")
CSS_PATH = Path(__file__).with_name("observatory.css")
FAVICON_PATH = Path(__file__).with_name("favicon.ico")
FAVICON_SVG_PATH = Path(__file__).with_name("favicon.svg")
APPLE_ICON_PATH = Path(__file__).with_name("apple-touch-icon.png")
OG_IMAGE_PATH = Path(__file__).with_name("og.png")
PAGE_TITLE = "BCRA Mini-RAG"
PAGE_KICKER = "RAG con citas"
PAGE_SUBTITLE = "Extracto no oficial de la normativa cambiaria (CAMEX) del BCRA."
PAGE_DESCRIPTION = (
    "Preguntá qué dice una Comunicación A del BCRA y recibí la cláusula citada, "
    "o un silencio honesto. Extracto no oficial de la normativa CAMEX."
)
PORTFOLIO_URL = "https://jahnog.github.io/"
SOURCE_URL = "https://github.com/jahnog/mini-rag-service"
WRITEUP_URL = "https://jahnog.github.io/BCRA-Mini-RAG/"
THEME_COLOR = "#050821"
FAVICON_HREF = "/favicon.ico"
FAVICON_SVG_HREF = "/favicon.svg"
APPLE_ICON_HREF = "/apple-touch-icon.png"
OG_IMAGE_HREF = "/og.png"
GRADIO_HEADER_IMAGE = (
    "https://raw.githubusercontent.com/gradio-app/gradio/main/"
    "js/_website/src/lib/assets/img/header-image.jpg"
)
_META_RE = re.compile(r"<meta\b([^>]*)/?>", re.IGNORECASE | re.DOTALL)
_ATTR_RE = re.compile(r"""([^\s=]+)\s*=\s*(["'])(.*?)\2""", re.DOTALL)
_GRADIO_HREF_RE = re.compile(
    r"""href=(["'])https://gradio\.app/?\1""",
    re.IGNORECASE,
)
_HTML_TAG_RE = re.compile(r"<html\b([^>]*)>", re.IGNORECASE)
_LANG_ATTR_RE = re.compile(r"""\slang=(["'])[^"']*\1""", re.IGNORECASE)
_CLASS_ATTR_RE = re.compile(r"""\sclass=(["'])([^"']*)\1""", re.IGNORECASE)
_VIEWPORT_RE = re.compile(
    r"""<meta\s+name=(["'])viewport\1\s+content=(["'])[^"']*\2\s*/?>""", re.IGNORECASE
)
VIEWPORT_CONTENT = "width=device-width, initial-scale=1, viewport-fit=cover"
_DROP_CARD_KEYS = frozenset({"twitter:creator"})
_SET_CARD_KEYS = frozenset(
    {
        "og:title",
        "twitter:title",
        "og:description",
        "twitter:description",
        "og:image",
        "twitter:image",
        "og:url",
    }
)
TEXT = "#ffffff"
TEXT_SUBDUED = "#b5c5e8"
SURFACE = "#121548"
SURFACE_STRONG = "#0b123d"
BORDER = "rgba(181, 197, 232, 0.28)"
BORDER_STRONG = "#425cc7"
ACCENT = "#f4b223"
ACCENT_STRONG = "#425cc7"
INPUT_BG = "#0b123d"
SECONDARY_BG = "#0b123d"
PRIMARY_FILL = "#f4b223"
PRIMARY_TEXT = "#121548"
SELECTED_FILL = "rgba(244, 178, 35, 0.22)"


def weblab_css_path() -> Path:
    return WEBLAB_CSS_PATH


def observatory_css_path() -> Path:
    return CSS_PATH


def observatory_css_paths() -> list[Path]:
    return [WEBLAB_CSS_PATH, CSS_PATH]


def observatory_favicon_path() -> Path:
    return FAVICON_PATH


def observatory_favicon_svg_path() -> Path:
    return FAVICON_SVG_PATH


def observatory_apple_icon_path() -> Path:
    return APPLE_ICON_PATH


def observatory_og_image_path() -> Path:
    return OG_IMAGE_PATH


def card_image_url(origin: str = "") -> str:
    origin = origin.rstrip("/")
    if origin.startswith(("http://", "https://")):
        return f"{origin}{OG_IMAGE_HREF}"
    return OG_IMAGE_HREF


def card_page_url(origin: str = "") -> str:
    origin = origin.rstrip("/")
    if origin.startswith(("http://", "https://")):
        return f"{origin}/"
    return "/"


def _family_html_tag(match: re.Match[str]) -> str:
    """Force lang="es" and class="wl-page" on the root element, once."""
    attrs = _LANG_ATTR_RE.sub("", match.group(1))
    class_match = _CLASS_ATTR_RE.search(attrs)
    if class_match is None:
        attrs += ' class="wl-page"'
    elif "wl-page" not in class_match.group(2).split():
        attrs = _CLASS_ATTR_RE.sub(
            lambda m: f' class={m.group(1)}{m.group(2)} wl-page{m.group(1)}', attrs, count=1
        )
    return f'<html lang="es"{attrs}>'


def rewrite_gradio_html(html: str, *, origin: str = "") -> str:
    image = card_image_url(origin)
    page = card_page_url(origin)
    values = {
        "og:title": PAGE_TITLE,
        "twitter:title": PAGE_TITLE,
        "og:description": PAGE_DESCRIPTION,
        "twitter:description": PAGE_DESCRIPTION,
        "og:image": image,
        "twitter:image": image,
        "og:url": page,
    }

    def replace_meta(match: re.Match[str]) -> str:
        attrs = {
            name.lower(): value for name, _, value in _ATTR_RE.findall(match.group(1))
        }
        key = (attrs.get("property") or attrs.get("name") or "").lower()
        if key in _DROP_CARD_KEYS:
            return ""
        if key not in _SET_CARD_KEYS:
            return match.group(0)
        kind = "property" if "property" in attrs else "name"
        content = html_lib.escape(values[key], quote=True)
        return f'<meta {kind}="{key}" content="{content}" />'

    rewritten = _META_RE.sub(replace_meta, html)
    rewritten = rewritten.replace(GRADIO_HEADER_IMAGE, image)
    # The page is Spanish and must say so before any script runs; Gradio
    # ships lang="en" and a viewport without viewport-fit.
    rewritten = _HTML_TAG_RE.sub(_family_html_tag, rewritten, count=1)
    rewritten = _VIEWPORT_RE.sub(
        f'<meta name="viewport" content="{VIEWPORT_CONTENT}" />', rewritten, count=1
    )
    return _GRADIO_HREF_RE.sub('href="/"', rewritten)


_MATOMO_BAD_CHARS = re.compile(r"""[\s'"<>\\]""")
_MATOMO_SITE_ID = re.compile(r"^[0-9]+$")


def normalized_matomo_url(url: str) -> str | None:
    raw = (url or "").strip()
    if not raw or _MATOMO_BAD_CHARS.search(raw):
        return None
    if "javascript:" in raw.lower():
        return None
    parsed = urlparse(raw)
    if parsed.scheme != "https" or not parsed.netloc:
        return None
    if parsed.username or parsed.password:
        return None
    if parsed.params or parsed.query or parsed.fragment:
        return None
    path = parsed.path or "/"
    if not path.endswith("/"):
        path += "/"
    return urlunparse(("https", parsed.netloc, path, "", "", ""))


def matomo_snippet(url: str = "", site_id: str = "") -> str:
    origin = normalized_matomo_url(url)
    sid = (site_id or "").strip()
    if origin is None or not _MATOMO_SITE_ID.fullmatch(sid):
        return ""
    tracker = json.dumps(origin + "matomo.php")
    script = json.dumps(origin + "matomo.js")
    sid_js = json.dumps(sid)
    return (
        "<script>(function(){"
        "var host=(location.hostname||'').toLowerCase();"
        "var loop=host==='localhost'||host==='127.0.0.1'"
        "||host==='::1'||host==='[::1]';"
        "var forced=/(?:^|[?&])matomo=1(?:&|$)/.test(location.search||'');"
        "if(loop&&!forced)return;"
        "var _paq=window._paq=window._paq||[];"
        '_paq.push(["disableCookies"]);'
        '_paq.push(["setDoNotTrack",true]);'
        f"_paq.push(['setTrackerUrl',{tracker}]);"
        f"_paq.push(['setSiteId',{sid_js}]);"
        '_paq.push(["enableLinkTracking"]);'
        '_paq.push(["enableHeartBeatTimer",15]);'
        '_paq.push(["trackPageView"]);'
        'var d=document,g=d.createElement("script"),'
        's=d.getElementsByTagName("script")[0];'
        "g.async=true;"
        f"g.src={script};"
        "if(s&&s.parentNode)s.parentNode.insertBefore(g,s);"
        "else (d.head||d.documentElement).appendChild(g);"
        "})();</script>"
    )


def observatory_head(*, matomo_url: str = "", matomo_site_id: str = "") -> str:
    description = html_lib.escape(PAGE_DESCRIPTION, quote=True)
    return (
        f"<title>{PAGE_TITLE}</title>"
        f'<meta name="description" content="{description}">'
        f'<meta name="theme-color" content="{THEME_COLOR}">'
        f'<link rel="icon" href="{FAVICON_HREF}" sizes="48x48">'
        f'<link rel="icon" href="{FAVICON_SVG_HREF}" type="image/svg+xml">'
        f'<link rel="apple-touch-icon" href="{APPLE_ICON_HREF}">'
        f'<meta property="og:type" content="website">'
        f'<meta property="og:title" content="{PAGE_TITLE}">'
        f'<meta property="og:description" content="{PAGE_DESCRIPTION}">'
        f'<meta property="og:image" content="{OG_IMAGE_HREF}">'
        f'<meta property="og:url" content="/">'
        f'<meta name="twitter:title" content="{PAGE_TITLE}">'
        f'<meta name="twitter:description" content="{PAGE_DESCRIPTION}">'
        f'<meta name="twitter:image" content="{OG_IMAGE_HREF}">'
        '<meta name="twitter:card" content="summary_large_image">'
        '<script>document.documentElement.lang="es";</script>'
        + matomo_snippet(matomo_url, matomo_site_id)
    )


def topbar_html() -> str:
    """Family topbar: category kicker, the product name as the page h1, one
    line of subtitle, and the Portfolio · Source · Write-up nav."""
    return (
        '<header class="wl-topbar" id="observatory-brand">'
        '<div class="wl-brand">'
        f'<p class="wl-kicker">{html_lib.escape(PAGE_KICKER)}</p>'
        f'<h1 class="wl-title">{html_lib.escape(PAGE_TITLE)}</h1>'
        f'<p class="wl-subtitle">{html_lib.escape(PAGE_SUBTITLE)}</p>'
        "</div>"
        '<nav class="wl-nav" aria-label="Sitio">'
        f'<a href="{PORTFOLIO_URL}">Portfolio</a>'
        f'<a href="{SOURCE_URL}">Código</a>'
        f'<a href="{WRITEUP_URL}">Write-up</a>'
        "</nav>"
        "</header>"
    )


def footer_html(disclaimer: str) -> str:
    """Family footer: the portfolio line, then the site's own disclaimer."""
    return (
        '<footer class="wl-footer" id="observatory-footer">'
        "<p>Parte del portfolio en "
        f'<a href="{PORTFOLIO_URL}">jahnog.github.io</a> · '
        f'<a href="{SOURCE_URL}">Código</a></p>'
        f"<p>{html_lib.escape(disclaimer)}</p>"
        "</footer>"
    )


def observatory_js() -> str:
    return f"""
() => {{
  document.title = {PAGE_TITLE!r};
  document.documentElement.lang = "es";
  document.documentElement.classList.add("dark", "wl-page");
  document.body.classList.add("dark");
}}
"""


def observatory_theme() -> Base:
    fills = dict(
        body_background_fill=THEME_COLOR,
        body_background_fill_dark=THEME_COLOR,
        body_text_color=TEXT,
        body_text_color_dark=TEXT,
        body_text_color_subdued=TEXT_SUBDUED,
        body_text_color_subdued_dark=TEXT_SUBDUED,
        background_fill_primary=SURFACE,
        background_fill_primary_dark=SURFACE,
        background_fill_secondary=SURFACE_STRONG,
        background_fill_secondary_dark=SURFACE_STRONG,
        block_background_fill=SURFACE,
        block_background_fill_dark=SURFACE,
        block_border_color=BORDER,
        block_border_color_dark=BORDER,
        block_label_background_fill=SURFACE,
        block_label_background_fill_dark=SURFACE,
        block_label_text_color=TEXT,
        block_label_text_color_dark=TEXT,
        block_title_text_color=TEXT,
        block_title_text_color_dark=TEXT,
        panel_background_fill=SURFACE_STRONG,
        panel_background_fill_dark=SURFACE_STRONG,
        panel_border_color=BORDER,
        panel_border_color_dark=BORDER,
        block_radius="8px",
        border_color_accent=ACCENT,
        border_color_accent_dark=ACCENT,
        color_accent=ACCENT,
        link_text_color=TEXT_SUBDUED,
        link_text_color_dark=TEXT_SUBDUED,
        accordion_text_color=TEXT,
        accordion_text_color_dark=TEXT,
        input_background_fill=INPUT_BG,
        input_background_fill_dark=INPUT_BG,
        input_border_color=BORDER_STRONG,
        input_border_color_dark=BORDER_STRONG,
        input_placeholder_color=TEXT_SUBDUED,
        input_placeholder_color_dark=TEXT_SUBDUED,
        button_primary_background_fill=PRIMARY_FILL,
        button_primary_background_fill_dark=PRIMARY_FILL,
        button_primary_text_color=PRIMARY_TEXT,
        button_primary_text_color_dark=PRIMARY_TEXT,
        button_secondary_background_fill=SECONDARY_BG,
        button_secondary_background_fill_dark=SECONDARY_BG,
        button_secondary_text_color=TEXT,
        button_secondary_text_color_dark=TEXT,
        checkbox_label_background_fill=SECONDARY_BG,
        checkbox_label_background_fill_dark=SECONDARY_BG,
        checkbox_label_background_fill_selected=SELECTED_FILL,
        checkbox_label_background_fill_selected_dark=SELECTED_FILL,
        checkbox_label_text_color=TEXT,
        checkbox_label_text_color_dark=TEXT,
        checkbox_label_text_color_selected=TEXT,
        checkbox_label_text_color_selected_dark=TEXT,
        checkbox_label_border_color=BORDER,
        checkbox_label_border_color_dark=BORDER,
        checkbox_label_border_color_selected=ACCENT,
        checkbox_label_border_color_selected_dark=ACCENT,
    )
    return Base(
        primary_hue=gr.themes.colors.amber,
        secondary_hue=gr.themes.colors.blue,
        neutral_hue=gr.themes.colors.slate,
        font=GoogleFont("Sora", weights=(400, 500, 600, 700)),
    ).set(**fills)
