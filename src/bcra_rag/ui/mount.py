"""Mount the Gradio page on the API app, with its static assets and HTML post-processing."""

from __future__ import annotations

from typing import Any

import gradio as gr
from fastapi import FastAPI
from fastapi.responses import FileResponse, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

from bcra_rag.ui.theme import (
    observatory_apple_icon_path,
    observatory_css_paths,
    observatory_favicon_path,
    observatory_favicon_svg_path,
    observatory_head,
    observatory_js,
    observatory_og_image_path,
    observatory_theme,
    rewrite_gradio_html,
    weblab_css_path,
)


class RewriteGradioHtml(BaseHTTPMiddleware):
    """Middleware that post-processes HTML pages served by Gradio."""

    async def dispatch(self, request: Request, call_next: Any) -> Any:
        """Buffer HTML responses and run them through `rewrite_gradio_html`.

        Non-HTML responses pass through untouched. The content-length header is
        dropped because the rewritten body has a different size.
        """
        response = await call_next(request)
        content_type = response.headers.get("content-type", "")
        if "text/html" not in content_type:
            return response
        body = bytearray()
        async for chunk in response.body_iterator:
            body.extend(chunk)
        html = rewrite_gradio_html(
            body.decode("utf-8", errors="replace"),
            origin=str(request.base_url).rstrip("/"),
        )
        headers = dict(response.headers)
        headers.pop("content-length", None)
        return Response(
            content=html,
            status_code=response.status_code,
            headers=headers,
            media_type=content_type,
        )


def mount_observatory_ui(api: FastAPI, blocks: gr.Blocks) -> FastAPI:
    """Mount the Gradio UI on the API app with its static asset routes and HTML middleware."""

    def serve_social_preview_image() -> FileResponse:
        """Serve the Open Graph preview image."""
        return FileResponse(observatory_og_image_path(), media_type="image/png")

    def serve_svg_favicon() -> FileResponse:
        """Serve the SVG favicon."""
        return FileResponse(observatory_favicon_svg_path(), media_type="image/svg+xml")

    def serve_apple_touch_icon() -> FileResponse:
        """Serve the Apple touch icon."""
        return FileResponse(observatory_apple_icon_path(), media_type="image/png")

    def serve_family_stylesheet() -> FileResponse:
        """Serve the shared family stylesheet."""
        return FileResponse(weblab_css_path(), media_type="text/css")

    api.add_api_route(
        "/og.png", serve_social_preview_image, methods=["GET"], include_in_schema=False
    )
    api.add_api_route(
        "/favicon.svg", serve_svg_favicon, methods=["GET"], include_in_schema=False
    )
    api.add_api_route(
        "/apple-touch-icon.png",
        serve_apple_touch_icon,
        methods=["GET"],
        include_in_schema=False,
    )
    api.add_api_route(
        "/weblab.css", serve_family_stylesheet, methods=["GET"], include_in_schema=False
    )
    api.add_middleware(RewriteGradioHtml)
    mounted: FastAPI = gr.mount_gradio_app(
        api,
        blocks,
        path="/",
        theme=observatory_theme(),
        css_paths=observatory_css_paths(),
        head=observatory_head(),
        js=observatory_js(),
        footer_links=[],
        run_history=False,
        favicon_path=str(observatory_favicon_path()),
    )
    return mounted
