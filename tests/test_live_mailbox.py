from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from bcra_rag.auth.mail_copy import OTP_SUBJECT, otp_body
from tests.features.live.mailbox import (
    DEFAULT_OTP_TTL_S,
    FakeMailbox,
    ImapMailbox,
    ImapSettings,
    MailboxError,
    MailboxTimeout,
    OtpMail,
    assert_no_new_otp,
    consume_used,
    find_leftover_otp,
    find_new_otp,
    parse_imap_internaldate,
    parse_otp_code,
    wait_for_new_otp,
)

NOW = datetime(2026, 9, 8, 12, 0, tzinfo=UTC)
CODE = "123456"


def _mail(
    *,
    uid: str = "1",
    code: str = CODE,
    date: datetime = NOW,
    unseen: bool = True,
    subject: str = OTP_SUBJECT,
    body: str | None = None,
) -> OtpMail:
    return OtpMail(
        uid=uid,
        subject=subject,
        body=body if body is not None else otp_body(code, ttl_s=300),
        date=date,
        unseen=unseen,
    )


def test_internaldate_keeps_zone_instead_of_local_tuple() -> None:
    utc = parse_imap_internaldate(
        b'6 (UID 6 INTERNALDATE "08-Sep-2026 22:23:51 +0000" BODY[] {12}'
    )
    assert utc == datetime(2026, 9, 8, 22, 23, 51, tzinfo=UTC)
    minus_three = parse_imap_internaldate(
        'INTERNALDATE "08-Sep-2026 19:23:51 -0300"'
    )
    assert minus_three is not None
    assert minus_three.astimezone(UTC) == datetime(2026, 9, 8, 22, 23, 51, tzinfo=UTC)
    assert parse_imap_internaldate("no stamp") is None


def test_parse_otp_from_body_not_subject() -> None:
    body = otp_body(CODE, ttl_s=300)
    assert parse_otp_code(subject=OTP_SUBJECT, body=body) == CODE
    assert CODE not in OTP_SUBJECT
    with pytest.raises(MailboxError, match="body"):
        parse_otp_code(subject=OTP_SUBJECT, body="sin codigo")
    with pytest.raises(MailboxError, match="subject"):
        parse_otp_code(subject=f"{OTP_SUBJECT} {CODE}", body=body)


def test_leftover_unseen_reuse_within_ttl() -> None:
    leftover = _mail(uid="7", date=NOW - timedelta(seconds=60))
    box = FakeMailbox([leftover])
    found = find_leftover_otp(box, now=NOW, ttl_s=DEFAULT_OTP_TTL_S)
    assert found is not None
    assert found.uid == "7"
    assert found.code == CODE


def test_ttl_bounded_search_ignores_old_unseen() -> None:
    stale = _mail(uid="old", date=NOW - timedelta(seconds=DEFAULT_OTP_TTL_S + 1))
    fresh = _mail(uid="new", date=NOW - timedelta(seconds=10))
    box = FakeMailbox([stale, fresh])
    found = find_leftover_otp(box, now=NOW, ttl_s=DEFAULT_OTP_TTL_S)
    assert found is not None
    assert found.uid == "new"
    only_stale = FakeMailbox([stale])
    assert find_leftover_otp(only_stale, now=NOW, ttl_s=DEFAULT_OTP_TTL_S) is None


def test_used_message_must_not_be_reused_after_verify() -> None:
    mail = _mail(uid="used")
    box = FakeMailbox([mail])
    consume_used(box, mail)
    assert find_leftover_otp(box, now=NOW) is None
    assert find_new_otp(box, since=NOW - timedelta(seconds=1)) is None
    assert all(item.deleted for item in box.items)


def test_no_new_message_within_bound() -> None:
    box = FakeMailbox()
    sleeps: list[float] = []
    assert_no_new_otp(box, since=NOW, wait_s=10, sleep=sleeps.append)
    assert sleeps == [10]
    box.add(_mail(uid="late", date=NOW + timedelta(seconds=1)))
    with pytest.raises(MailboxError, match="unexpected new"):
        assert_no_new_otp(box, since=NOW, wait_s=0, sleep=lambda _: None)


def test_wait_for_new_otp_polls_until_date_at_least_since() -> None:
    pending = _mail(uid="arrived", date=NOW + timedelta(seconds=2))

    class Delayed(FakeMailbox):
        def __init__(self) -> None:
            super().__init__()
            self.hits = 0

        def refresh(self) -> None:
            self.hits += 1
            if self.hits >= 3:
                self.add(pending)

    delayed = Delayed()
    found = wait_for_new_otp(
        delayed, since=NOW, timeout_s=5, poll_s=0, sleep=lambda _: None
    )
    assert found.uid == "arrived"
    empty = FakeMailbox()
    with pytest.raises(MailboxTimeout):
        wait_for_new_otp(empty, since=NOW, timeout_s=0, poll_s=0, sleep=lambda _: None)


def test_imap_settings_ssl_and_plain_ports(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LIVE_IMAP_HOST", "imap.example")
    monkeypatch.setenv("LIVE_IMAP_USER", "ops@example.com")
    monkeypatch.setenv("LIVE_IMAP_PASSWORD", "secret")
    monkeypatch.delenv("LIVE_IMAP_PORT", raising=False)
    monkeypatch.setenv("LIVE_IMAP_SSL", "true")
    ssl_settings = ImapSettings.from_env()
    assert ssl_settings.port == 993
    assert ssl_settings.ssl is True
    monkeypatch.setenv("LIVE_IMAP_SSL", "false")
    plain = ImapSettings.from_env()
    assert plain.ssl is False
    assert plain.port == 143
    monkeypatch.setenv("LIVE_IMAP_PORT", "1143")
    custom = ImapSettings.from_env()
    assert custom.port == 1143
    assert custom.ssl is False


def test_connect_imap_plain_is_not_starttls(monkeypatch: pytest.MonkeyPatch) -> None:
    from tests.features.live import mailbox as mailbox_mod

    created: list[str] = []

    class FakeIMAP:
        def __init__(self, host: str, port: int) -> None:
            created.append(f"plain:{host}:{port}")

        def login(self, user: str, password: str) -> None:
            return None

        def select(self, mailbox: str) -> tuple[str, list[bytes]]:
            return "OK", [b"1"]

        def starttls(self) -> None:
            raise AssertionError("STARTTLS is unsupported")

    class FakeSSL(FakeIMAP):
        def __init__(self, host: str, port: int) -> None:
            created.append(f"ssl:{host}:{port}")

    monkeypatch.setattr(mailbox_mod.imaplib, "IMAP4", FakeIMAP)
    monkeypatch.setattr(mailbox_mod.imaplib, "IMAP4_SSL", FakeSSL)
    client = mailbox_mod.connect_imap(
        ImapSettings(
            host="imap.example",
            port=143,
            user="u",
            password="p",
            mailbox="INBOX",
            ssl=False,
        )
    )
    assert isinstance(client, FakeIMAP)
    assert created == ["plain:imap.example:143"]
    ssl_client = mailbox_mod.connect_imap(
        ImapSettings(
            host="imap.example",
            port=993,
            user="u",
            password="p",
            mailbox="INBOX",
            ssl=True,
        )
    )
    assert isinstance(ssl_client, FakeSSL)
    assert created[-1] == "ssl:imap.example:993"


def test_from_env_requires_host_user_password(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("LIVE_IMAP_HOST", raising=False)
    monkeypatch.delenv("LIVE_IMAP_USER", raising=False)
    monkeypatch.delenv("LIVE_IMAP_PASSWORD", raising=False)
    with pytest.raises(MailboxError, match="LIVE_IMAP_HOST"):
        ImapSettings.from_env()


def test_imap_fetch_peeks_and_keeps_utc_internaldate(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from email.message import EmailMessage

    from tests.features.live import mailbox as mailbox_mod

    message = EmailMessage()
    message["Subject"] = OTP_SUBJECT
    message["From"] = "bot@example.com"
    message["To"] = "ops@example.com"
    message.set_content(otp_body(CODE, ttl_s=300))
    raw = message.as_bytes()
    fetched: list[tuple[str, str, str]] = []

    class FakeIMAP:
        def uid(self, cmd: str, uid: str, spec: str) -> tuple[str, list[object]]:
            fetched.append((cmd, uid, spec))
            meta = (
                b'1 (UID 1 FLAGS () INTERNALDATE "08-Sep-2026 22:23:51 +0000" '
                b"BODY[] {" + str(len(raw)).encode() + b"}"
            )
            return "OK", [(meta, raw)]

        def close(self) -> None:
            return None

        def logout(self) -> None:
            return None

    monkeypatch.setattr(mailbox_mod, "connect_imap", lambda settings: FakeIMAP())
    box = ImapMailbox(
        ImapSettings(
            host="imap.example",
            port=993,
            user="u",
            password="p",
            mailbox="INBOX",
            ssl=True,
        )
    )
    mail = box._fetch_one("1")
    assert fetched == [("FETCH", "1", "(FLAGS INTERNALDATE BODY.PEEK[])")]
    assert mail is not None
    assert mail.date == datetime(2026, 9, 8, 22, 23, 51, tzinfo=UTC)
    assert mail.unseen is True
    assert mail.code == CODE


def test_new_mail_ignores_older_than_since() -> None:
    older = _mail(uid="old", date=NOW - timedelta(seconds=5))
    newer = _mail(uid="new", date=NOW + timedelta(seconds=1))
    box = FakeMailbox([older, newer])
    found = find_new_otp(box, since=NOW)
    assert found is not None
    assert found.uid == "new"
