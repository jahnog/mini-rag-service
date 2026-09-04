from __future__ import annotations

from pathlib import Path

import gradio as gr
from gradio.themes import Base, GoogleFont

CSS_PATH = Path(__file__).with_name("observatory.css")
THEME_COLOR = "#04111d"
TEXT = "#f4fbff"
TEXT_SUBDUED = "rgba(210, 228, 237, 0.8)"
SURFACE = "rgba(8, 26, 43, 0.78)"
SURFACE_STRONG = "rgba(5, 18, 30, 0.9)"
BORDER = "rgba(124, 203, 214, 0.16)"
BORDER_STRONG = "rgba(124, 203, 214, 0.3)"
ACCENT = "#72d6cb"
ACCENT_STRONG = "#9ce7df"
INPUT_BG = "rgba(4, 15, 25, 0.55)"
SECONDARY_BG = "rgba(4, 15, 25, 0.42)"
PRIMARY_FILL = "linear-gradient(135deg, #9ce7df, #72d6cb)"
PRIMARY_TEXT = "#03101c"
SELECTED_FILL = "rgba(114, 214, 203, 0.22)"


def observatory_css_path() -> Path:
    return CSS_PATH


def observatory_head() -> str:
    return (
        f'<meta name="theme-color" content="{THEME_COLOR}">'
        '<script>document.documentElement.lang="es";</script>'
    )


def observatory_js() -> str:
    return """
() => {
  document.documentElement.lang = "es";
  document.documentElement.classList.add("dark");
  document.body.classList.add("dark");
}
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
        block_radius="28px",
        border_color_accent=ACCENT,
        border_color_accent_dark=ACCENT,
        color_accent=ACCENT,
        link_text_color=ACCENT_STRONG,
        link_text_color_dark=ACCENT_STRONG,
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
        primary_hue=gr.themes.colors.teal,
        secondary_hue=gr.themes.colors.sky,
        neutral_hue=gr.themes.colors.slate,
        font=GoogleFont("Sora", weights=(400, 500, 600, 700)),
    ).set(**fills)
