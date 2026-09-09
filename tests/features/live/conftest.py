from __future__ import annotations

from collections.abc import Iterator
from typing import Any

import httpx
import pytest

from tests.features.live.http_client import (
    authenticate_from_mailbox,
    make_client,
)
from tests.features.live.mailbox import ImapMailbox, live_email


@pytest.fixture(scope="session")
def live_imap_mailbox() -> Iterator[ImapMailbox]:
    box = ImapMailbox()
    try:
        yield box
    finally:
        box.close()


@pytest.fixture(scope="session")
def live_http_session(live_imap_mailbox: ImapMailbox) -> Iterator[dict[str, Any]]:
    client = make_client()
    email = live_email()
    if not email:
        raise pytest.UsageError("LIVE_EMAIL or LIVE_IMAP_USER is required")
    auth = authenticate_from_mailbox(client, live_imap_mailbox, email)
    try:
        yield {
            "client": client,
            "email": email,
            "code": auth.mail.code,
            "mailbox": live_imap_mailbox,
            "otp_mail": auth.mail,
            "set_cookie": auth.set_cookie,
            "otp_sent": auth.sent_new,
        }
    finally:
        client.close()


@pytest.fixture
def live_anon_client() -> Iterator[httpx.Client]:
    client = make_client()
    try:
        yield client
    finally:
        client.close()


@pytest.fixture(scope="session")
def live_chromium() -> Iterator[Any]:
    from tests.features.live.browser import launch_chromium

    browser, stop = launch_chromium()
    try:
        yield browser
    finally:
        stop()


@pytest.fixture
def logged_out_observatory(live_chromium: Any) -> Iterator[dict[str, Any]]:
    from tests.features.live.browser import new_page

    context, page = new_page(live_chromium)
    try:
        yield {"page": page, "context": context, "http": None, "seed": None}
    finally:
        context.close()


@pytest.fixture
def cloned_observatory(
    live_chromium: Any, live_http_session: dict[str, Any]
) -> Iterator[dict[str, Any]]:
    from tests.features.live.browser import new_page, seed_weather

    context, page = new_page(live_chromium, client=live_http_session["client"])
    seed_weather(page)
    try:
        yield {
            "page": page,
            "context": context,
            "http": live_http_session,
            "seed": "Madrid",
        }
    finally:
        context.close()


@pytest.fixture(scope="session")
def shared_observatory(
    live_chromium: Any, live_http_session: dict[str, Any]
) -> Iterator[dict[str, Any]]:
    from tests.features.live.browser import new_page, seed_weather

    context, page = new_page(live_chromium, client=live_http_session["client"])
    seed_weather(page)
    try:
        yield {
            "page": page,
            "context": context,
            "http": live_http_session,
            "seed": "Madrid",
        }
    finally:
        context.close()
