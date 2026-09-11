"""Test-only IMAP helper for live OTP mail. The serving process does not speak IMAP."""

from __future__ import annotations

import email
import imaplib
import os
import re
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass, replace
from datetime import UTC, datetime, timedelta, timezone
from email.header import decode_header, make_header
from email.message import Message
from email.utils import parsedate_to_datetime
from typing import Protocol

from bcra_rag.auth.mail_copy import OTP_CODE_RE, OTP_SUBJECT

_INTERNALDATE_RE = re.compile(
    r'INTERNALDATE "(?P<day>\d{1,2})-(?P<mon>[A-Za-z]{3})-(?P<year>\d{4}) '
    r"(?P<hour>\d{2}):(?P<minute>\d{2}):(?P<second>\d{2}) (?P<zone>[+-]\d{4})\""
)
_IMAP_MONTHS = {
    "jan": 1,
    "feb": 2,
    "mar": 3,
    "apr": 4,
    "may": 5,
    "jun": 6,
    "jul": 7,
    "aug": 8,
    "sep": 9,
    "oct": 10,
    "nov": 11,
    "dec": 12,
}
DEFAULT_OTP_TTL_S = 300.0
DEFAULT_POLL_TIMEOUT_S = 30.0
DEFAULT_POLL_S = 1.0
DEFAULT_MISS_WAIT_S = 10.0


class MailboxError(RuntimeError):
    """IMAP or OTP-parse failure."""


class MailboxTimeout(MailboxError):
    """No matching OTP mail within the poll bound."""


def parse_imap_internaldate(raw: bytes | str) -> datetime | None:
    """Parse IMAP INTERNALDATE keeping its zone.

    imaplib.Internaldate2tuple returns local wall time. Tagging that as UTC
    shifts a just-sent OTP by the host offset, so live waits miss it.
    """
    text = raw.decode("utf-8", errors="replace") if isinstance(raw, bytes) else raw
    match = _INTERNALDATE_RE.search(text)
    if match is None:
        return None
    month = _IMAP_MONTHS.get(match.group("mon").lower())
    if month is None:
        return None
    zone = match.group("zone")
    sign = 1 if zone[0] == "+" else -1
    tz = timezone(sign * timedelta(hours=int(zone[1:3]), minutes=int(zone[3:5])))
    return datetime(
        int(match.group("year")),
        month,
        int(match.group("day")),
        int(match.group("hour")),
        int(match.group("minute")),
        int(match.group("second")),
        tzinfo=tz,
    )


LOGIN_URL_RE = re.compile(r"(https?://[^\s]+/auth/link/[A-Za-z0-9_-]+)")
LOGIN_TOKEN_RE = re.compile(r"/auth/link/([A-Za-z0-9_-]+)")


def parse_otp_code(*, subject: str, body: str) -> str:
    match = OTP_CODE_RE.search(body or "")
    if match is None:
        raise MailboxError("no 6-digit secret in body")
    code = match.group(1)
    if re.search(r"\d{6}", subject or ""):
        raise MailboxError("subject must not contain the 6-digit secret")
    return code


def parse_login_url(*, subject: str, body: str) -> str:
    match = LOGIN_URL_RE.search(body or "")
    if match is None:
        raise MailboxError("no login URL in body")
    url = match.group(1)
    token_match = LOGIN_TOKEN_RE.search(url)
    token = token_match.group(1) if token_match else ""
    if token and token in (subject or ""):
        raise MailboxError("subject must not contain the login token")
    return url


@dataclass(frozen=True)
class OtpMail:
    uid: str
    subject: str
    body: str
    date: datetime
    unseen: bool = True
    deleted: bool = False

    @property
    def code(self) -> str:
        return parse_otp_code(subject=self.subject, body=self.body)

    @property
    def login_url(self) -> str:
        return parse_login_url(subject=self.subject, body=self.body)


class Mailbox(Protocol):
    def messages(self) -> Sequence[OtpMail]: ...

    def mark_used(self, uid: str) -> None: ...

    def refresh(self) -> None: ...


def _aware(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def matching_otp(
    mails: Sequence[OtpMail], *, subject: str = OTP_SUBJECT
) -> list[OtpMail]:
    return [mail for mail in mails if not mail.deleted and mail.subject == subject]


def snapshot_otp_uids(
    mailbox: Mailbox, *, subject: str = OTP_SUBJECT
) -> frozenset[str]:
    mailbox.refresh()
    return frozenset(
        mail.uid for mail in matching_otp(mailbox.messages(), subject=subject)
    )


def find_new_otp(
    mailbox: Mailbox,
    *,
    since: datetime,
    subject: str = OTP_SUBJECT,
    seen_uids: frozenset[str] | None = None,
) -> OtpMail | None:
    mailbox.refresh()
    cutoff = _aware(since)
    candidates: list[OtpMail] = []
    for mail in matching_otp(mailbox.messages(), subject=subject):
        if seen_uids is not None:
            if mail.uid in seen_uids:
                continue
        elif _aware(mail.date) < cutoff:
            continue
        candidates.append(mail)
    if not candidates:
        return None
    return max(candidates, key=lambda mail: _aware(mail.date))


def find_leftover_otp(
    mailbox: Mailbox,
    *,
    now: datetime,
    ttl_s: float = DEFAULT_OTP_TTL_S,
    subject: str = OTP_SUBJECT,
) -> OtpMail | None:
    mailbox.refresh()
    cutoff = _aware(now) - timedelta(seconds=ttl_s)
    candidates = [
        mail
        for mail in matching_otp(mailbox.messages(), subject=subject)
        if mail.unseen and _aware(mail.date) >= cutoff
    ]
    if not candidates:
        return None
    return max(candidates, key=lambda mail: _aware(mail.date))


def wait_for_new_otp(
    mailbox: Mailbox,
    *,
    since: datetime,
    timeout_s: float = DEFAULT_POLL_TIMEOUT_S,
    poll_s: float = DEFAULT_POLL_S,
    subject: str = OTP_SUBJECT,
    seen_uids: frozenset[str] | None = None,
    sleep: Callable[[float], None] = time.sleep,
) -> OtpMail:
    deadline = time.monotonic() + timeout_s
    while True:
        found = find_new_otp(
            mailbox, since=since, subject=subject, seen_uids=seen_uids
        )
        if found is not None:
            return found
        if time.monotonic() >= deadline:
            raise MailboxTimeout("no new one-time-secret message within bound")
        sleep(poll_s)


def assert_no_new_otp(
    mailbox: Mailbox,
    *,
    since: datetime,
    wait_s: float = DEFAULT_MISS_WAIT_S,
    subject: str = OTP_SUBJECT,
    sleep: Callable[[float], None] = time.sleep,
) -> None:
    sleep(wait_s)
    if find_new_otp(mailbox, since=since, subject=subject) is not None:
        raise MailboxError("unexpected new one-time-secret message")


def consume_used(mailbox: Mailbox, mail: OtpMail) -> None:
    mailbox.mark_used(mail.uid)


@dataclass
class FakeMailbox:
    """In-memory IMAP stand-in for default-suite unit tests (no network)."""

    items: list[OtpMail]

    def __init__(self, items: Sequence[OtpMail] | None = None) -> None:
        self.items = list(items or [])

    def add(self, mail: OtpMail) -> None:
        self.items.append(mail)

    def messages(self) -> list[OtpMail]:
        return [mail for mail in self.items if not mail.deleted]

    def mark_used(self, uid: str) -> None:
        self.items = [
            replace(mail, deleted=True, unseen=False) if mail.uid == uid else mail
            for mail in self.items
        ]

    def refresh(self) -> None:
        return


def _env_bool(name: str, default: bool) -> bool:
    raw = os.environ.get(name)
    if raw is None or not raw.strip():
        return default
    return raw.strip().lower() not in {"0", "false", "no", "off"}


@dataclass(frozen=True)
class ImapSettings:
    host: str
    port: int
    user: str
    password: str
    mailbox: str
    ssl: bool

    @classmethod
    def from_env(cls) -> ImapSettings:
        host = os.environ.get("LIVE_IMAP_HOST", "").strip()
        user = os.environ.get("LIVE_IMAP_USER", "").strip()
        password = os.environ.get("LIVE_IMAP_PASSWORD", "")
        if not host or not user or not password:
            raise MailboxError(
                "LIVE_IMAP_HOST, LIVE_IMAP_USER, and LIVE_IMAP_PASSWORD are required"
            )
        ssl = _env_bool("LIVE_IMAP_SSL", True)
        port_raw = os.environ.get("LIVE_IMAP_PORT", "").strip()
        port = int(port_raw) if port_raw else (993 if ssl else 143)
        mailbox = os.environ.get("LIVE_IMAP_MAILBOX", "INBOX").strip() or "INBOX"
        return cls(
            host=host, port=port, user=user, password=password, mailbox=mailbox, ssl=ssl
        )


def live_email() -> str:
    return (
        os.environ.get("LIVE_EMAIL", "").strip()
        or os.environ.get("LIVE_IMAP_USER", "").strip()
    )


def connect_imap(settings: ImapSettings) -> imaplib.IMAP4:
    if settings.ssl:
        client: imaplib.IMAP4 = imaplib.IMAP4_SSL(settings.host, settings.port)
    else:
        client = imaplib.IMAP4(settings.host, settings.port)
    client.login(settings.user, settings.password)
    typ, _ = client.select(settings.mailbox)
    if typ != "OK":
        raise MailboxError(f"cannot select mailbox {settings.mailbox}")
    return client


def _decode_header(raw: str | None) -> str:
    if not raw:
        return ""
    return str(make_header(decode_header(raw)))


def _body_text(message: Message) -> str:
    if message.is_multipart():
        parts: list[str] = []
        for part in message.walk():
            if part.get_content_type() != "text/plain":
                continue
            payload = part.get_payload(decode=True)
            charset = part.get_content_charset() or "utf-8"
            if isinstance(payload, bytes):
                parts.append(payload.decode(charset, errors="replace"))
        return "\n".join(parts)
    payload = message.get_payload(decode=True)
    charset = message.get_content_charset() or "utf-8"
    if isinstance(payload, bytes):
        return payload.decode(charset, errors="replace")
    return str(payload or "")


def _mail_date(message: Message, internal: datetime | None) -> datetime:
    if internal is not None:
        return _aware(internal)
    raw = message.get("Date")
    if raw:
        try:
            return _aware(parsedate_to_datetime(raw))
        except (TypeError, ValueError, OverflowError):
            pass
    return datetime.now(UTC)


class ImapMailbox:
    def __init__(self, settings: ImapSettings | None = None) -> None:
        self.settings = settings or ImapSettings.from_env()
        self._client = connect_imap(self.settings)
        self._cache: list[OtpMail] = []

    def close(self) -> None:
        try:
            self._client.close()
        except Exception:
            pass
        try:
            self._client.logout()
        except Exception:
            pass

    def _reconnect(self) -> None:
        self.close()
        self._client = connect_imap(self.settings)
        self._cache = []

    def _ensure_connected(self) -> None:
        try:
            typ, _ = self._client.noop()
            if typ != "OK":
                raise MailboxError("IMAP NOOP failed")
        except Exception:
            self._reconnect()

    def refresh(self) -> None:
        self._ensure_connected()
        try:
            self._cache = self._fetch_all()
        except Exception:
            self._reconnect()
            self._cache = self._fetch_all()

    def messages(self) -> list[OtpMail]:
        if not self._cache:
            self.refresh()
        return list(self._cache)

    def mark_used(self, uid: str) -> None:
        typ, _ = self._client.uid("STORE", uid, "+FLAGS", r"(\Deleted \Seen)")
        if typ != "OK":
            raise MailboxError(f"cannot mark used uid {uid}")
        try:
            self._client.expunge()
        except Exception:
            pass
        self._cache = [
            replace(mail, deleted=True, unseen=False) if mail.uid == uid else mail
            for mail in self._cache
        ]

    def _fetch_all(self) -> list[OtpMail]:
        typ, data = self._client.uid("SEARCH", None, "ALL")
        if typ != "OK":
            raise MailboxError(f"IMAP SEARCH failed: {typ}")
        if not data or not data[0]:
            return []
        uids = data[0].split()
        out: list[OtpMail] = []
        for uid in uids:
            mail = self._fetch_one(uid.decode() if isinstance(uid, bytes) else str(uid))
            if mail is not None:
                out.append(mail)
        return out

    def _fetch_one(self, uid: str) -> OtpMail | None:
        typ, data = self._client.uid(
            "FETCH", uid, "(FLAGS INTERNALDATE BODY.PEEK[])"
        )
        if typ != "OK" or not data:
            return None
        flags = ""
        internal: datetime | None = None
        raw: bytes | None = None
        for item in data:
            if not isinstance(item, tuple) or len(item) < 2:
                continue
            meta = item[0]
            payload = item[1]
            if isinstance(meta, bytes):
                text = meta.decode("utf-8", errors="replace")
                flags = text
                parsed = parse_imap_internaldate(meta)
                if parsed is not None:
                    internal = parsed
            if isinstance(payload, bytes):
                raw = payload
        if raw is None:
            return None
        message = email.message_from_bytes(raw)
        subject = _decode_header(message.get("Subject"))
        unseen = r"\Seen" not in flags
        deleted = r"\Deleted" in flags
        return OtpMail(
            uid=uid,
            subject=subject,
            body=_body_text(message),
            date=_mail_date(message, internal),
            unseen=unseen,
            deleted=deleted,
        )
