from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from bcra_rag.auth.errors import AuthRejected, AuthUnavailable
from bcra_rag.auth.fake import FakeMailer
from bcra_rag.auth.mail_copy import OTP_CODE_RE, otp_code_from_text
from bcra_rag.auth.origin import cookie_secure, origin_matches
from bcra_rag.auth.ports import Mailer
from bcra_rag.auth.service import AuthService, RequestOtpResult, normalize_email
from bcra_rag.auth.settings import SECRET_MIN_LEN, AuthSettings
from bcra_rag.auth.smtp import SmtpMailer


@dataclass
class AuthModule:
    settings: AuthSettings
    service: AuthService
    mailer: Mailer


def build_auth(
    *,
    settings: AuthSettings | None = None,
    mailer: Mailer | None = None,
) -> AuthModule:
    resolved = settings or AuthSettings()
    resolved_mailer = mailer or SmtpMailer(resolved)
    service = AuthService(resolved, resolved_mailer)
    return AuthModule(settings=resolved, service=service, mailer=resolved_mailer)


def mount_auth(api: Any, auth: AuthModule) -> None:
    from bcra_rag.auth.routes import build_router

    api.state.auth = auth
    api.include_router(build_router(auth))


def email_from_request(auth: AuthModule, request: Any) -> str | None:
    cookies = getattr(request, "cookies", None)
    value = None
    if cookies is not None:
        getter = getattr(cookies, "get", None)
        if callable(getter):
            value = getter(auth.settings.cookie_name)
    if not value:
        headers = getattr(request, "headers", None)
        if headers is not None:
            header_get = getattr(headers, "get", None)
            if callable(header_get):
                raw = header_get("cookie") or header_get("Cookie")
                if raw:
                    prefix = auth.settings.cookie_name + "="
                    for part in str(raw).split(";"):
                        piece = part.strip()
                        if piece.startswith(prefix):
                            value = piece[len(prefix) :]
                            break
    if not value:
        return None
    return auth.service.email_from_cookie(str(value))


__all__ = [
    "AuthModule",
    "AuthRejected",
    "AuthService",
    "AuthSettings",
    "AuthUnavailable",
    "FakeMailer",
    "Mailer",
    "OTP_CODE_RE",
    "RequestOtpResult",
    "SECRET_MIN_LEN",
    "SmtpMailer",
    "build_auth",
    "cookie_secure",
    "email_from_request",
    "mount_auth",
    "normalize_email",
    "origin_matches",
    "otp_code_from_text",
]
