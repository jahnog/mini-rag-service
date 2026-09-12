#!/usr/bin/env python3
"""Send AUTH_SMTP_* mail when laptop production smoke fails. Stdlib only."""

from __future__ import annotations

import argparse
import os
import smtplib
import sys
from email.message import EmailMessage
from pathlib import Path

TAIL_LINES = 80


def _expand_placeholder(raw: str) -> str:
    text = (raw or "").strip()
    if len(text) >= 3 and text.startswith("${") and text.endswith("}"):
        return (os.environ.get(text[2:-1]) or "").strip()
    return text


def notify(
    *,
    exit_code: str,
    duration_s: str,
    log_path: Path | None,
    environ: dict[str, str] | None = None,
) -> None:
    env = environ if environ is not None else dict(os.environ)
    to_addr = (
        env.get("PROD_SMOKE_NOTIFY_TO") or env.get("LIVE_EMAIL") or ""
    ).strip()
    host = (env.get("AUTH_SMTP_HOST") or "").strip()
    from_addr = (env.get("AUTH_SMTP_FROM") or "").strip()
    if not to_addr or not host or not from_addr:
        raise RuntimeError("missing PROD_SMOKE_NOTIFY_TO/LIVE_EMAIL or AUTH_SMTP_*")
    port = int(env.get("AUTH_SMTP_PORT") or "587")
    user = (env.get("AUTH_SMTP_USER") or "").strip()
    password = _expand_placeholder(env.get("AUTH_SMTP_PASSWORD") or "")
    starttls = (env.get("AUTH_SMTP_STARTTLS") or "true").strip().lower() not in {
        "0",
        "false",
        "no",
    }
    timeout_s = float(env.get("AUTH_SMTP_TIMEOUT_S") or "10")
    timed_out = exit_code in {"124", "137"}
    subject = (
        "BCRA Mini-RAG production smoke TIMED OUT"
        if timed_out
        else "BCRA Mini-RAG production smoke FAILED"
    )
    tail = ""
    if log_path is not None and log_path.is_file():
        lines = log_path.read_text(encoding="utf-8", errors="replace").splitlines()
        tail = "\n".join(lines[-TAIL_LINES:])
    body = (
        f"exit={exit_code} duration_s={duration_s}\n"
        f"timed_out={timed_out}\n\n"
        f"{tail or '(no log tail)'}\n"
    )
    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = from_addr
    message["To"] = to_addr
    message.set_content(body)
    with smtplib.SMTP(host, port, timeout=timeout_s) as smtp:
        if starttls:
            smtp.starttls()
        if user:
            smtp.login(user, password)
        smtp.send_message(message)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--exit-code", required=True)
    parser.add_argument("--duration", required=True)
    parser.add_argument("--log", default="")
    args = parser.parse_args(argv)
    log_path = Path(args.log) if args.log else None
    try:
        notify(
            exit_code=args.exit_code,
            duration_s=args.duration,
            log_path=log_path,
        )
    except Exception as exc:
        print(f"notify failed: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
