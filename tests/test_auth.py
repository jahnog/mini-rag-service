from __future__ import annotations

import os
import re
import threading
import time
from dataclasses import dataclass
from types import SimpleNamespace

import pytest

from bcra_rag.auth import (
    AuthRejected,
    AuthService,
    AuthSettings,
    AuthUnavailable,
    FakeMailer,
    SmtpMailer,
    build_auth,
    cookie_secure,
    normalize_email,
    origin_matches,
    otp_code_from_text,
)
from bcra_rag.auth.mail_copy import otp_html_body
from bcra_rag.ports import __all__ as PORTS
from bcra_rag.settings import Settings

SECRET = "s" * 32
OPS = "ops@example.com"


@dataclass
class Clock:
    t: float = 1_000_000.0

    def __call__(self) -> float:
        return self.t

    def advance(self, seconds: float) -> None:
        self.t += seconds


def _service(
    *,
    mailer: FakeMailer | None = None,
    allowed: str = OPS,
    clock: Clock | None = None,
    **kwargs: object,
) -> tuple[AuthService, FakeMailer, Clock]:
    settings = AuthSettings(
        _env_file=None, secret=SECRET, allowed_emails=allowed, **kwargs
    )  # type: ignore[arg-type]
    resolved = mailer or FakeMailer(ttl_s=settings.otp_ttl_s)
    tick = clock or Clock()
    service = AuthService(settings, resolved, time_fn=tick)
    return service, resolved, tick


def test_auth_settings_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    for key in list(os.environ):
        if key.startswith("AUTH_"):
            monkeypatch.delenv(key, raising=False)
    settings = AuthSettings(_env_file=None)
    assert settings.secret == ""
    assert settings.allowed_emails == ""
    assert settings.cookie_name == "session"
    assert settings.session_days == 1
    assert settings.otp_ttl_s == 300
    assert settings.otp_digits == 6
    assert settings.trust_proxy is False
    assert settings.public_origin == ""
    assert settings.smtp_host == ""
    assert settings.smtp_port == 587
    assert settings.smtp_starttls is True
    assert settings.smtp_timeout_s == 10.0
    assert settings.max_distinct_emails_per_ip_day == 5
    assert settings.max_sends_per_email_minute == 1
    assert settings.max_sends_per_email_day == 10
    assert settings.max_sends_per_ip_day == 20
    assert settings.max_verify_fails_per_otp == 5
    assert settings.max_verify_fails_per_ip_hour == 15
    assert settings.verify_ip_cooldown_s == 900
    assert settings.min_verify_interval_s == 2.0
    assert settings.max_sends_per_process_day == 200
    assert settings.session_ttl_s == 86400
    assert settings.secret_ok is False


def test_auth_settings_reads_prefix(monkeypatch) -> None:
    monkeypatch.setenv("AUTH_SECRET", "s" * 32)
    monkeypatch.setenv("AUTH_ALLOWED_EMAILS", "ops@example.com")
    monkeypatch.setenv("AUTH_COOKIE_NAME", "session")
    settings = AuthSettings()
    assert settings.secret == "s" * 32
    assert settings.allowed_emails == "ops@example.com"
    assert settings.secret_ok is True


def test_rag_settings_ignore_auth_env(monkeypatch) -> None:
    monkeypatch.setenv("AUTH_SECRET", "s" * 32)
    monkeypatch.setenv("AUTH_ALLOWED_EMAILS", "ops@example.com")
    settings = Settings()
    assert not hasattr(settings, "secret") or getattr(settings, "secret", None) is None
    assert not hasattr(settings, "auth_secret")
    assert not hasattr(settings, "allowed_emails")


def test_ports_remain_five_rag_names() -> None:
    assert PORTS == [
        "CatalogPort",
        "ExtractorPort",
        "IndexPort",
        "LlmPort",
        "SessionStore",
    ]


def test_build_auth_uses_fake_mailer() -> None:
    mailer = FakeMailer()
    module = build_auth(
        settings=AuthSettings(
            _env_file=None, secret="s" * 32, allowed_emails="ops@example.com"
        ),
        mailer=mailer,
    )
    assert module.mailer is mailer
    assert module.settings.cookie_name == "session"
    assert isinstance(module.mailer, FakeMailer)


def test_smtp_mailer_unconfigured_without_host() -> None:
    mailer = SmtpMailer(AuthSettings(_env_file=None))
    assert mailer.configured is False


def test_normalize_plus_tag() -> None:
    assert normalize_email("Ops+staff@Example.com") == "ops@example.com"


def _code_from(mailer: FakeMailer) -> str:
    code = otp_code_from_text(mailer.sent[-1].body)
    assert code
    return code


def _token_from(mailer: FakeMailer) -> str:
    match = re.search(r"/auth/link/([A-Za-z0-9_-]+)", mailer.sent[-1].body)
    assert match
    return match.group(1)


def test_allowlisted_email_receives_six_digit_secret() -> None:
    service, mailer, _ = _service()
    service.request_otp(OPS, "1.1.1.1")
    assert len(mailer.sent) == 1
    assert mailer.sent[0].to == OPS
    assert otp_code_from_text(mailer.sent[0].body)
    assert otp_code_from_text(mailer.sent[0].html)
    assert not re.search(r"\d{6}", mailer.sent[0].subject)


def test_allowlist_miss_looks_like_success() -> None:
    service, mailer, _ = _service()
    service.request_otp("stranger@example.com", "1.1.1.1")
    assert mailer.sent == []


def test_empty_allowlist_sends_nothing() -> None:
    service, mailer, _ = _service(allowed="")
    service.request_otp(OPS, "1.1.1.1")
    assert mailer.sent == []


def test_wildcard_allowlist_sends_to_any_well_formed_email() -> None:
    service, mailer, _ = _service(allowed="*")
    service.request_otp("stranger@example.com", "1.1.1.1")
    assert len(mailer.sent) == 1
    assert mailer.sent[0].to == "stranger@example.com"
    assert otp_code_from_text(mailer.sent[0].body)
    assert not re.search(r"\d{6}", mailer.sent[0].subject)


def test_wildcard_with_other_entries_still_sends() -> None:
    service, mailer, _ = _service(allowed="*,ops@example.com")
    service.request_otp("stranger@example.com", "1.1.1.1")
    assert len(mailer.sent) == 1
    assert mailer.sent[0].to == "stranger@example.com"


def test_plus_tag_under_wildcard_sends_to_requested_and_shares_minute_bucket() -> None:
    service, mailer, clock = _service(allowed="*", otp_ttl_s=5)
    service.request_otp("ops+staff@example.com", "1.1.1.1")
    assert mailer.sent[0].to == "ops+staff@example.com"
    clock.advance(6)
    with pytest.raises(AuthRejected) as exc:
        service.request_otp("ops+other@example.com", "1.1.1.1")
    assert exc.value.status == 429


def test_plus_tag_matches_allowlist_and_counts_as_same_mailbox() -> None:
    service, mailer, clock = _service(otp_ttl_s=5)
    service.request_otp("ops+staff@example.com", "1.1.1.1")
    assert mailer.sent[0].to == "ops+staff@example.com"
    clock.advance(6)
    with pytest.raises(AuthRejected) as exc:
        service.request_otp("ops+other@example.com", "1.1.1.1")
    assert exc.value.status == 429


def test_second_request_while_otp_live_does_not_send_or_rotate() -> None:
    service, mailer, _ = _service()
    service.request_otp(OPS, "1.1.1.1")
    first = _code_from(mailer)
    service.request_otp(OPS, "1.1.1.1")
    assert len(mailer.sent) == 1
    cookie = service.verify_otp(OPS, first, "1.1.1.1")
    assert service.email_from_cookie(cookie) == OPS


def test_request_after_expiry_sends_new_code() -> None:
    service, mailer, clock = _service()
    service.request_otp(OPS, "1.1.1.1")
    first = _code_from(mailer)
    clock.advance(301)
    service.request_otp(OPS, "1.1.1.1")
    second = _code_from(mailer)
    assert len(mailer.sent) == 2
    clock.advance(3)
    with pytest.raises(AuthRejected) as exc:
        service.verify_otp(OPS, first, "1.1.1.1")
    assert exc.value.status == 401
    clock.advance(3)
    cookie = service.verify_otp(OPS, second, "1.1.1.1")
    assert service.email_from_cookie(cookie) == OPS


def test_correct_code_authenticates_for_a_day() -> None:
    service, mailer, clock = _service()
    service.request_otp(OPS, "1.1.1.1")
    cookie = service.verify_otp(OPS, _code_from(mailer), "1.1.1.1")
    clock.advance(86400 - 10)
    assert service.email_from_cookie(cookie) == OPS
    clock.advance(20)
    assert service.email_from_cookie(cookie) is None


def test_expired_secret_fails_generically() -> None:
    service, mailer, clock = _service()
    service.request_otp(OPS, "1.1.1.1")
    code = _code_from(mailer)
    clock.advance(301)
    with pytest.raises(AuthRejected) as expired:
        service.verify_otp(OPS, code, "1.1.1.1")
    clock.advance(3)
    service.request_otp(OPS, "1.1.1.1")
    clock.advance(3)
    with pytest.raises(AuthRejected) as wrong:
        service.verify_otp(OPS, "000000", "1.1.1.1")
    assert expired.value.status == wrong.value.status == 401
    assert expired.value.detail == wrong.value.detail


def test_five_failures_burn_the_secret() -> None:
    service, mailer, clock = _service()
    service.request_otp(OPS, "1.1.1.1")
    code = _code_from(mailer)
    for _ in range(5):
        clock.advance(3)
        with pytest.raises(AuthRejected):
            service.verify_otp(OPS, "000000", "1.1.1.1")
    clock.advance(3)
    with pytest.raises(AuthRejected) as exc:
        service.verify_otp(OPS, code, "1.1.1.1")
    assert exc.value.status == 401


def test_secret_is_single_use() -> None:
    service, mailer, clock = _service()
    service.request_otp(OPS, "1.1.1.1")
    code = _code_from(mailer)
    service.verify_otp(OPS, code, "1.1.1.1")
    clock.advance(3)
    with pytest.raises(AuthRejected):
        service.verify_otp(OPS, code, "1.1.1.1")


def test_sixth_distinct_email_from_one_ip_is_429() -> None:
    service, mailer, clock = _service(
        allowed=",".join(f"user{i}@example.com" for i in range(6))
    )
    for i in range(5):
        clock.advance(61)
        service.request_otp(f"user{i}@example.com", "9.9.9.9")
    with pytest.raises(AuthRejected) as exc:
        service.request_otp("user5@example.com", "9.9.9.9")
    assert exc.value.status == 429
    assert mailer.sent[-1].to == "user4@example.com"
    assert len(mailer.sent) == 5


def test_second_send_within_a_minute_is_429() -> None:
    service, mailer, clock = _service(otp_ttl_s=5)
    service.request_otp(OPS, "1.1.1.1")
    clock.advance(6)
    with pytest.raises(AuthRejected) as exc:
        service.request_otp(OPS, "1.1.1.1")
    assert exc.value.status == 429
    assert exc.value.retry_after is not None
    assert len(mailer.sent) == 1


def test_malformed_email_rejected() -> None:
    service, mailer, _ = _service()
    with pytest.raises(AuthRejected) as exc:
        service.request_otp("not-an-email\r\nBcc:x@y.z", "1.1.1.1")
    assert exc.value.status == 422
    assert mailer.sent == []


def test_missing_secret_unavailable() -> None:
    mailer = FakeMailer()
    service = AuthService(
        AuthSettings(_env_file=None, secret="", allowed_emails=OPS), mailer
    )
    with pytest.raises(AuthUnavailable):
        service.request_otp(OPS, "1.1.1.1")
    assert mailer.sent == []


def test_unconfigured_mail_sends_nothing() -> None:
    mailer = FakeMailer(configured=False)
    service, _, _ = _service(mailer=mailer)
    service.request_otp(OPS, "1.1.1.1")
    assert mailer.sent == []


def test_origin_matches_scheme_host_and_port() -> None:
    assert origin_matches("https://rag.example", "https://rag.example:443")
    assert origin_matches("https://rag.example:443", "https://rag.example")
    assert not origin_matches("https://rag.example", "http://rag.example")
    assert not origin_matches("https://rag.example:8443", "https://rag.example")
    assert not origin_matches("https://rag.example", "")


def test_cookie_secure_signals() -> None:
    http = SimpleNamespace(headers={}, url=SimpleNamespace(scheme="http"))
    assert cookie_secure(http, AuthSettings(_env_file=None)) is False
    public = AuthSettings(_env_file=None, public_origin="https://rag.example")
    assert cookie_secure(http, public) is True
    origin_https = SimpleNamespace(
        headers={"origin": "https://rag.example"},
        url=SimpleNamespace(scheme="http"),
    )
    assert cookie_secure(origin_https, AuthSettings(_env_file=None)) is True
    forwarded = SimpleNamespace(
        headers={"x-forwarded-proto": "https"},
        url=SimpleNamespace(scheme="http"),
    )
    assert cookie_secure(forwarded, AuthSettings(_env_file=None)) is False
    trusted = AuthSettings(_env_file=None, trust_proxy=True)
    assert cookie_secure(forwarded, trusted) is True


class _BoomMailer:
    configured = True

    def send_otp(
        self, *, to: str, code: str, login_url: str | None = None
    ) -> None:
        raise RuntimeError("smtp down")


def test_smtp_failure_does_not_install_otp() -> None:
    service, _, _ = _service(mailer=_BoomMailer())  # type: ignore[arg-type]
    with pytest.raises(AuthUnavailable):
        service.request_otp(OPS, "1.1.1.1")
    with pytest.raises(AuthRejected) as exc:
        service.verify_otp(OPS, "000000", "1.1.1.1")
    assert exc.value.status == 401


def test_smtp_failure_counts_toward_send_limit() -> None:
    settings = AuthSettings(_env_file=None, secret=SECRET, allowed_emails=OPS)
    clock = Clock()
    service = AuthService(settings, _BoomMailer(), time_fn=clock)
    with pytest.raises(AuthUnavailable):
        service.request_otp(OPS, "1.1.1.1")
    with pytest.raises(AuthRejected) as exc:
        service.request_otp(OPS, "1.1.1.1")
    assert exc.value.status == 429
    clock.advance(61)
    mailer = FakeMailer()
    service.mailer = mailer
    service.request_otp(OPS, "1.1.1.1")
    assert len(mailer.sent) == 1


def test_smtp_mailer_passes_timeout(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, object] = {}

    class FakeSMTP:
        def __init__(self, host: str, port: int, timeout: object = None) -> None:
            captured["timeout"] = timeout

        def __enter__(self) -> FakeSMTP:
            return self

        def __exit__(self, *args: object) -> bool:
            return False

        def starttls(self) -> None:
            return None

        def send_message(self, message: object) -> None:
            del message

    monkeypatch.setattr("bcra_rag.auth.smtp.smtplib.SMTP", FakeSMTP)
    mailer = SmtpMailer(
        AuthSettings(
            _env_file=None,
            smtp_host="smtp.example",
            smtp_from="bot@example.com",
            smtp_user="",
        )
    )
    mailer.send_otp(to=OPS, code="123456")
    assert captured["timeout"] == 10.0


def test_concurrent_requests_send_at_most_one_mail() -> None:
    class SlowMailer(FakeMailer):
        def send_otp(
            self, *, to: str, code: str, login_url: str | None = None
        ) -> None:
            time.sleep(0.2)
            super().send_otp(to=to, code=code, login_url=login_url)

    mailer = SlowMailer()
    service, _, _ = _service(mailer=mailer)
    errors: list[BaseException] = []

    def worker() -> None:
        try:
            service.request_otp(OPS, "1.1.1.1")
        except BaseException as exc:
            errors.append(exc)

    threads = [threading.Thread(target=worker) for _ in range(2)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert errors == []
    assert len(mailer.sent) == 1
    cookie = service.verify_otp(OPS, _code_from(mailer), "1.1.1.1")
    assert service.email_from_cookie(cookie) == OPS


def test_logs_omit_secret_and_email(caplog: pytest.LogCaptureFixture) -> None:
    service, mailer, _ = _service()
    with caplog.at_level("INFO"):
        service.request_otp(OPS, "1.1.1.1")
    text = caplog.text + str(caplog.records)
    code = _code_from(mailer)
    assert code not in text
    assert OPS not in text


def test_html_mail_escapes_and_has_observatory_look() -> None:
    html = otp_html_body(
        "123456",
        ttl_s=300,
        login_url='https://rag.example/auth/link/a&b"c',
    )
    assert "lang=\"es\"" in html
    assert "Iniciar sesión" in html
    assert 'rel="noopener noreferrer"' in html
    assert "#04111d" in html
    assert "#72d6cb" in html
    assert "#03101c" in html
    assert "<img" not in html.lower()
    assert OPS not in html
    assert "a&amp;b" in html
    assert "&quot;" in html
    assert "Tu código de acceso es 123456" in html


def test_public_origin_adds_login_url() -> None:
    service, mailer, _ = _service(public_origin="https://rag.example/")
    issued = service.request_otp(OPS, "1.1.1.1")
    token = _token_from(mailer)
    assert issued.login_url == f"https://rag.example/auth/link/{token}"
    assert issued.intent_nonce
    assert OPS not in issued.login_url
    assert _code_from(mailer) not in issued.login_url
    assert "https://rag.example//" not in mailer.sent[0].body
    assert issued.login_url in mailer.sent[0].body
    assert issued.login_url in mailer.sent[0].html
    raw = service._otps[OPS]
    assert raw.link_digest
    assert token not in raw.link_digest
    assert token not in raw.digest


def test_unset_origin_omits_login_url() -> None:
    service, mailer, _ = _service()
    issued = service.request_otp(OPS, "1.1.1.1")
    assert issued.login_url is None
    assert "/auth/link/" not in mailer.sent[0].body
    assert "/auth/link/" not in mailer.sent[0].html
    assert otp_code_from_text(mailer.sent[0].body)


def test_coalesce_keeps_token_and_intent() -> None:
    service, mailer, _ = _service(public_origin="https://rag.example")
    first = service.request_otp(OPS, "1.1.1.1")
    token = _token_from(mailer)
    nonce = first.intent_nonce
    second = service.request_otp(OPS, "1.1.1.1")
    assert len(mailer.sent) == 1
    assert second.intent_nonce == nonce
    assert service.inspect_link(token) == OPS
    assert service.intent_matches(token, nonce or "")


def test_verify_burns_login_token() -> None:
    service, mailer, _ = _service(public_origin="https://rag.example")
    service.request_otp(OPS, "1.1.1.1")
    token = _token_from(mailer)
    service.verify_otp(OPS, _code_from(mailer), "1.1.1.1")
    assert service.inspect_link(token) is None
    with pytest.raises(AuthRejected):
        service.consume_link(token, "1.1.1.1")


def test_consume_link_burns_otp() -> None:
    service, mailer, _ = _service(public_origin="https://rag.example")
    service.request_otp(OPS, "1.1.1.1")
    code = _code_from(mailer)
    token = _token_from(mailer)
    cookie = service.consume_link(token, "1.1.1.1")
    assert service.email_from_cookie(cookie) == OPS
    with pytest.raises(AuthRejected):
        service.verify_otp(OPS, code, "1.1.1.1")


def test_concurrent_link_consume_at_most_one_session() -> None:
    service, mailer, _ = _service(public_origin="https://rag.example")
    service.request_otp(OPS, "1.1.1.1")
    token = _token_from(mailer)
    results: list[str] = []
    errors: list[BaseException] = []

    def worker() -> None:
        try:
            results.append(service.consume_link(token, "1.1.1.1"))
        except BaseException as exc:
            errors.append(exc)

    threads = [threading.Thread(target=worker) for _ in range(2)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert len(results) == 1
    assert len(errors) == 1
    assert service.email_from_cookie(results[0]) == OPS


def test_logs_omit_login_token(caplog: pytest.LogCaptureFixture) -> None:
    service, mailer, _ = _service(public_origin="https://rag.example")
    with caplog.at_level("INFO"):
        service.request_otp(OPS, "1.1.1.1")
        token = _token_from(mailer)
        service.consume_link(token, "1.1.1.1")
    text = caplog.text + str(caplog.records)
    assert token not in text
    assert OPS not in text

