from __future__ import annotations

from pathlib import Path

import gradio as gr
from gradio.themes import Base, GoogleFont

CSS_PATH = Path(__file__).with_name("observatory.css")
THEME_COLOR = "#04111d"


def observatory_css_path() -> Path:
    return CSS_PATH


def observatory_head() -> str:
    return f'<meta name="theme-color" content="{THEME_COLOR}">'


def observatory_theme() -> Base:
    return Base(
        primary_hue=gr.themes.colors.teal,
        secondary_hue=gr.themes.colors.sky,
        neutral_hue=gr.themes.colors.slate,
        font=GoogleFont("Sora", weights=(400, 500, 600, 700)),
    ).set(
        body_background_fill_dark=THEME_COLOR,
        body_text_color_dark="#f4fbff",
        body_text_color_subdued_dark="rgba(210, 228, 237, 0.8)",
        background_fill_primary_dark="rgba(8, 26, 43, 0.78)",
        background_fill_secondary_dark="rgba(5, 18, 30, 0.9)",
        block_background_fill_dark="rgba(8, 26, 43, 0.78)",
        block_border_color_dark="rgba(124, 203, 214, 0.16)",
        block_radius="28px",
        border_color_accent_dark="#72d6cb",
        button_primary_background_fill_dark="linear-gradient(135deg, #9ce7df, #72d6cb)",
        button_primary_text_color_dark="#03101c",
        button_secondary_background_fill_dark="rgba(4, 15, 25, 0.42)",
        button_secondary_text_color_dark="#f4fbff",
        input_background_fill_dark="rgba(4, 15, 25, 0.55)",
        input_border_color_dark="rgba(124, 203, 214, 0.3)",
        input_placeholder_color_dark="rgba(210, 228, 237, 0.6)",
        color_accent="#72d6cb",
        link_text_color_dark="#9ce7df",
    )
