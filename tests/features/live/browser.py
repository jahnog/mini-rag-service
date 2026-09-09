"""Playwright helpers for live observatory scenarios (Chromium, live_ui only)."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any
from urllib.parse import urlparse

from tests.features.live.http_client import (
    ProcessLimiterError,
    cookie_name,
    live_base_url,
)

CHAT_TIMEOUT_MS = 240_000
WIDE = {"width": 1280, "height": 720}
NARROW = {"width": 375, "height": 812}


def launch_chromium() -> tuple[Any, Callable[[], None]]:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as exc:
        raise RuntimeError(
            "Chromium is required for live_ui; run `playwright install chromium`"
        ) from exc
    try:
        playwright = sync_playwright().start()
        browser = playwright.chromium.launch(headless=True)
    except Exception as exc:
        raise RuntimeError(
            "Chromium is required for live_ui; run `playwright install chromium`"
        ) from exc

    def stop() -> None:
        browser.close()
        playwright.stop()

    return browser, stop


def add_session_cookie(context: Any, client: Any, base_url: str) -> None:
    name = cookie_name()
    value = client.cookies.get(name)
    if not value:
        raise RuntimeError(f"missing session cookie {name}")
    parsed = urlparse(base_url)
    context.add_cookies(
        [
            {
                "name": name,
                "value": value,
                "url": base_url.rstrip("/") + "/",
                "httpOnly": True,
                "secure": parsed.scheme == "https",
                "sameSite": "Lax",
            }
        ]
    )


def new_page(browser: Any, *, client: Any | None = None) -> tuple[Any, Any]:
    context = browser.new_context()
    page = context.new_page()
    page.set_default_timeout(CHAT_TIMEOUT_MS)
    base = live_base_url()
    if client is not None:
        add_session_cookie(context, client, base)
    page.goto(base + "/", wait_until="domcontentloaded")
    page.locator("#observatory-shell").wait_for()
    return context, page


def field(page: Any, elem_id: str) -> Any:
    return page.locator(f"#{elem_id} textarea, #{elem_id} input").first


def click_id(page: Any, elem_id: str) -> None:
    root = page.locator(f"#{elem_id}")
    inner = root.locator("button")
    if inner.count() > 0:
        inner.first.click()
    else:
        root.click()


def visible(page: Any, selector: str) -> bool:
    loc = page.locator(selector).first
    try:
        return bool(loc.is_visible())
    except Exception:
        return False


def send_observatory_question(page: Any, message: str) -> dict[str, Any] | None:
    field(page, "observatory-input").fill(message)
    with page.expect_response(
        lambda response: "/chat" in response.url and response.request.method == "POST",
        timeout=CHAT_TIMEOUT_MS,
    ) as pending:
        click_id(page, "observatory-send")
    response = pending.value
    if response.status == 429:
        raise ProcessLimiterError(
            "HTTP 429 from the process limiter during observatory Enviar; "
            "restart the process or wait"
        )
    try:
        payload = response.json()
    except Exception:
        return None
    return payload if isinstance(payload, dict) else None


def seed_weather(page: Any) -> None:
    send_observatory_question(page, "What's the weather in Madrid?")
    page.locator("#observatory-chat").get_by_text("Madrid", exact=False).wait_for()


def select_vista(page: Any, label: str) -> None:
    page.get_by_text(label, exact=True).click()


def bounding(page: Any, selector: str) -> dict[str, float]:
    box = page.locator(selector).first.bounding_box()
    assert box is not None
    return box
