from __future__ import annotations

import importlib.util
import sys
from email.message import EmailMessage
from pathlib import Path
from types import ModuleType

import pytest

ROOT = Path(__file__).resolve().parents[1]
WRAPPER = ROOT / "scripts" / "run-prod-smoke-cron.sh"
NOTIFY = ROOT / "scripts" / "notify_prod_smoke_failure.py"
CRONTAB = ROOT / "scripts" / "prod-smoke.crontab"


def test_cron_wrapper_invariants() -> None:
    text = WRAPPER.read_text(encoding="utf-8")
    assert text.startswith("#!/usr/bin/env bash")
    assert "set -euo pipefail" in text
    assert "flock -n 9" in text
    assert "15m" in text
    assert "run-prod-smoke.sh" in text
    assert "direnv export bash" in text
    assert "PROD_SMOKE_NOTIFY_TO" in text
    assert "LIVE_EMAIL" in text
    assert "notify_prod_smoke_failure.py" in text
    assert "content" + "labstudy" not in text
    assert "ssd-" + "480" not in text


def test_crontab_example_is_daily_1011() -> None:
    text = CRONTAB.read_text(encoding="utf-8")
    assert "11 10 * * *" in text
    assert "run-prod-smoke-cron.sh" in text
    assert "MAILTO=" in text
    assert "content" + "labstudy" not in text


def _load_notify() -> ModuleType:
    spec = importlib.util.spec_from_file_location(
        "notify_prod_smoke_failure", NOTIFY
    )
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    sys.modules["notify_prod_smoke_failure"] = mod
    spec.loader.exec_module(mod)
    return mod


def test_notify_helper_uses_smtp_env_not_mailbox_literal() -> None:
    text = NOTIFY.read_text(encoding="utf-8")
    assert "AUTH_SMTP_HOST" in text
    assert "PROD_SMOKE_NOTIFY_TO" in text
    assert "LIVE_EMAIL" in text
    assert "smtplib" in text
    assert "content" + "labstudy" not in text


def test_notify_sends_on_failure(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    mod = _load_notify()
    sent: list[EmailMessage] = []

    class _Smtp:
        def __init__(self, *args: object, **kwargs: object) -> None:
            del args, kwargs

        def __enter__(self) -> _Smtp:
            return self

        def __exit__(self, *args: object) -> None:
            return None

        def starttls(self) -> None:
            return None

        def login(self, user: str, password: str) -> None:
            assert user == "botsender"
            assert password == "secret"

        def send_message(self, message: EmailMessage) -> None:
            sent.append(message)

    monkeypatch.setattr(mod.smtplib, "SMTP", _Smtp)
    log_path = tmp_path / "last.log"
    log_path.write_text("FAILED tests/prod/test_smoke.py::test_named_a3500\n", encoding="utf-8")
    mod.notify(
        exit_code="1",
        duration_s="12",
        log_path=log_path,
        environ={
            "PROD_SMOKE_NOTIFY_TO": "ops@example.com",
            "AUTH_SMTP_HOST": "mail.example.com",
            "AUTH_SMTP_FROM": "botsender@example.com",
            "AUTH_SMTP_USER": "botsender",
            "AUTH_SMTP_PASSWORD": "secret",
            "AUTH_SMTP_PORT": "587",
            "AUTH_SMTP_STARTTLS": "true",
        },
    )
    assert len(sent) == 1
    assert sent[0]["To"] == "ops@example.com"
    assert "FAILED" in sent[0]["Subject"]
    payload = sent[0].get_content()
    assert "test_named_a3500" in payload
    assert "exit=1" in payload


def test_notify_skips_without_smtp() -> None:
    mod = _load_notify()
    with pytest.raises(RuntimeError, match="missing"):
        mod.notify(exit_code="1", duration_s="1", log_path=None, environ={})
