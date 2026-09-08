from __future__ import annotations

import hashlib
import hmac
import re
import secrets
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime

import structlog

from bcra_rag.auth.cookies import read_session, sign_session
from bcra_rag.auth.errors import AuthRejected, AuthUnavailable
from bcra_rag.auth.ports import Mailer
from bcra_rag.auth.settings import AuthSettings

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
_MAX_EMAIL_LEN = 254
_log = structlog.get_logger("bcra_rag.auth")


@dataclass
class _Otp:
    digest: str
    expires: float
    fails: int = 0


@dataclass
class AuthService:
    settings: AuthSettings
    mailer: Mailer
    time_fn: Callable[[], float] = time.time
    _lock: threading.RLock = field(default_factory=threading.RLock)
    _otps: dict[str, _Otp] = field(default_factory=dict)
    _send_times_email: dict[str, list[float]] = field(default_factory=dict)
    _send_times_ip: dict[str, list[float]] = field(default_factory=dict)
    _emails_ip_day: dict[tuple[str, str], set[str]] = field(default_factory=dict)
    _verify_fails_ip: dict[str, list[float]] = field(default_factory=dict)
    _verify_last_email: dict[str, float] = field(default_factory=dict)
    _ip_lockout: dict[str, float] = field(default_factory=dict)
    _process_sends: list[float] = field(default_factory=list)

    def request_otp(self, email: str, ip: str) -> None:
        with self._lock:
            self._request_otp_locked(email, ip)

    def verify_otp(self, email: str, code: str, ip: str) -> str:
        with self._lock:
            return self._verify_otp_locked(email, code, ip)

    def _request_otp_locked(self, email: str, ip: str) -> None:
        self._require_secret()
        raw = self._validate_email(email)
        normalized = normalize_email(raw)
        now = self.time_fn()
        live = self._otps.get(normalized)
        if live is not None and now < live.expires:
            self._log(normalized, "sent")
            return
        self._enforce_send_limits(normalized, ip, now)
        self._record_send(normalized, ip, now)
        dummy = self._otp_digest(normalized, "000000")
        allowlist = {normalize_email(item) for item in self.settings.allowlist()}
        if not allowlist or normalized not in allowlist or not self.mailer.configured:
            hmac.compare_digest(dummy, dummy)
            self._log(normalized, "sent")
            return
        code = f"{secrets.randbelow(10 ** self.settings.otp_digits):0{self.settings.otp_digits}d}"
        try:
            self.mailer.send_otp(to=raw, code=code)
        except Exception as exc:
            self._log(normalized, "invalid")
            raise AuthUnavailable("authentication unavailable") from exc
        self._otps[normalized] = _Otp(
            digest=self._otp_digest(normalized, code),
            expires=now + self.settings.otp_ttl_s,
        )
        self._log(normalized, "sent")

    def _verify_otp_locked(self, email: str, code: str, ip: str) -> str:
        self._require_secret()
        raw = self._validate_email(email)
        normalized = normalize_email(raw)
        now = self.time_fn()
        self._enforce_verify_limits(normalized, ip, now)
        record = self._otps.get(normalized)
        candidate = (code or "").strip()
        digest = self._otp_digest(normalized, candidate)
        if (
            record is None
            or now >= record.expires
            or not hmac.compare_digest(record.digest, digest)
        ):
            self._register_verify_fail(normalized, ip, now, record)
            self._log(normalized, "invalid")
            raise AuthRejected(401, "invalid or expired code")
        del self._otps[normalized]
        self._log(normalized, "verified")
        return sign_session(
            email=normalized,
            secret=self.settings.secret,
            ttl_s=self.settings.session_ttl_s,
            now=now,
        )

    def email_from_cookie(self, value: str) -> str | None:
        if not self.settings.secret_ok:
            return None
        return read_session(
            value=value, secret=self.settings.secret, now=self.time_fn()
        )

    def _require_secret(self) -> None:
        if not self.settings.secret_ok:
            raise AuthUnavailable("authentication unavailable")

    def _validate_email(self, email: str) -> str:
        raw = (email or "").strip()
        if (
            not raw
            or len(raw) > _MAX_EMAIL_LEN
            or "\r" in raw
            or "\n" in raw
            or _EMAIL_RE.match(raw) is None
        ):
            raise AuthRejected(422, "invalid email")
        return raw.lower()

    def _otp_digest(self, email: str, code: str) -> str:
        payload = f"{email}:{code}".encode()
        return hmac.new(self.settings.secret.encode(), payload, hashlib.sha256).hexdigest()

    def _utc_day(self, now: float) -> str:
        return datetime.fromtimestamp(now, tz=UTC).strftime("%Y-%m-%d")

    def _prune(self, times: list[float], now: float, window: float) -> list[float]:
        return [ts for ts in times if now - ts < window]

    def _enforce_send_limits(self, email: str, ip: str, now: float) -> None:
        day = self._utc_day(now)
        process = self._prune(self._process_sends, now, 86400)
        self._process_sends = process
        if len(process) >= self.settings.max_sends_per_process_day:
            self._limited(email)
        ip_day_key = (ip, day)
        seen = set(self._emails_ip_day.get(ip_day_key, set()))
        if email not in seen and len(seen) >= self.settings.max_distinct_emails_per_ip_day:
            self._limited(email)
        email_sends = self._prune(self._send_times_email.get(email, []), now, 86400)
        self._send_times_email[email] = email_sends
        recent = [ts for ts in email_sends if now - ts < 60]
        if len(recent) >= self.settings.max_sends_per_email_minute:
            wait = max(1, int(60 - (now - recent[0])))
            self._limited(email, retry_after=wait)
        if len(email_sends) >= self.settings.max_sends_per_email_day:
            self._limited(email)
        ip_sends = self._prune(self._send_times_ip.get(ip, []), now, 86400)
        self._send_times_ip[ip] = ip_sends
        if len(ip_sends) >= self.settings.max_sends_per_ip_day:
            self._limited(email)

    def _record_send(self, email: str, ip: str, now: float) -> None:
        day = self._utc_day(now)
        self._process_sends.append(now)
        self._send_times_email.setdefault(email, []).append(now)
        self._send_times_ip.setdefault(ip, []).append(now)
        key = (ip, day)
        bucket = set(self._emails_ip_day.get(key, set()))
        bucket.add(email)
        self._emails_ip_day[key] = bucket

    def _enforce_verify_limits(self, email: str, ip: str, now: float) -> None:
        lockout = self._ip_lockout.get(ip, 0.0)
        if now < lockout:
            self._limited(email, retry_after=max(1, int(lockout - now)))
        last = self._verify_last_email.get(email, 0.0)
        gap = self.settings.min_verify_interval_s
        if now - last < gap:
            self._limited(email, retry_after=max(1, int(gap - (now - last))))
        fails = self._prune(self._verify_fails_ip.get(ip, []), now, 3600)
        self._verify_fails_ip[ip] = fails
        if len(fails) >= self.settings.max_verify_fails_per_ip_hour:
            until = now + self.settings.verify_ip_cooldown_s
            self._ip_lockout[ip] = until
            self._limited(email, retry_after=self.settings.verify_ip_cooldown_s)
        self._verify_last_email[email] = now

    def _register_verify_fail(
        self, email: str, ip: str, now: float, record: _Otp | None
    ) -> None:
        fails = self._prune(self._verify_fails_ip.get(ip, []), now, 3600)
        fails.append(now)
        self._verify_fails_ip[ip] = fails
        if record is not None:
            record.fails += 1
            if record.fails >= self.settings.max_verify_fails_per_otp:
                self._otps.pop(email, None)

    def _limited(self, email: str, retry_after: int | None = None) -> None:
        self._log(email, "limited")
        raise AuthRejected(429, "rate limit exceeded", retry_after=retry_after)

    def _log(self, email: str, outcome: str) -> None:
        prefix = hashlib.sha256(email.encode()).hexdigest()[:8]
        _log.info("auth", email_hash=prefix, outcome=outcome)


def normalize_email(email: str) -> str:
    trimmed = email.strip().lower()
    if "@" not in trimmed:
        return trimmed
    local, domain = trimmed.rsplit("@", 1)
    local = local.split("+", 1)[0]
    return f"{local}@{domain}"
