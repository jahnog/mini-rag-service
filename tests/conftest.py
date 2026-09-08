from __future__ import annotations

import os

import httpx
import pytest

DEFAULT_LIVE_BASE_URL = "http://127.0.0.1:8000"


def pytest_addoption(parser: pytest.Parser) -> None:
    parser.addoption(
        "--run-integration",
        action="store_true",
        default=False,
        help="run live BCRA integration tests",
    )
    parser.addoption(
        "--run-live-server",
        action="store_true",
        default=False,
        help="run live acceptance against an already-running local process",
    )


def live_base_url() -> str:
    return os.environ.get("LIVE_BASE_URL", DEFAULT_LIVE_BASE_URL).rstrip("/")


def pytest_sessionstart(session: pytest.Session) -> None:
    if not session.config.getoption("--run-live-server"):
        return
    from tests.features.live.http_client import live_base_url as resolved_base
    from tests.features.live.http_client import require_imap_env
    from tests.features.live.mailbox import MailboxError

    base = resolved_base()
    url = f"{base}/health"
    try:
        response = httpx.get(url, timeout=2.0)
        response.raise_for_status()
    except Exception as exc:
        raise pytest.UsageError(
            f"LIVE_BASE_URL unreachable: {base} (did not spawn uvicorn): {exc}"
        ) from exc
    try:
        require_imap_env()
    except MailboxError as exc:
        raise pytest.UsageError(str(exc)) from exc


def pytest_collection_modifyitems(
    config: pytest.Config, items: list[pytest.Item]
) -> None:
    if not config.getoption("--run-integration"):
        skip_integration = pytest.mark.skip(reason="live BCRA; pass --run-integration")
        for item in items:
            if "integration" in item.keywords:
                item.add_marker(skip_integration)
    if not config.getoption("--run-live-server"):
        skip_live = pytest.mark.skip(reason="live server; pass --run-live-server")
        for item in items:
            if "live_server" in item.keywords:
                item.add_marker(skip_live)
