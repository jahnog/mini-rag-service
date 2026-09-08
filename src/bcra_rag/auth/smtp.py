from __future__ import annotations

import smtplib
from email.message import EmailMessage

from bcra_rag.auth.mail_copy import OTP_SUBJECT, otp_body
from bcra_rag.auth.settings import AuthSettings


class SmtpMailer:
    def __init__(self, settings: AuthSettings) -> None:
        self._settings = settings

    @property
    def configured(self) -> bool:
        return bool(self._settings.smtp_host and self._settings.smtp_from)

    def send_otp(self, *, to: str, code: str) -> None:
        if not self.configured:
            return
        message = EmailMessage()
        message["Subject"] = OTP_SUBJECT
        message["From"] = self._settings.smtp_from
        message["To"] = to
        message.set_content(otp_body(code, ttl_s=self._settings.otp_ttl_s))
        with smtplib.SMTP(
            self._settings.smtp_host,
            self._settings.smtp_port,
            timeout=self._settings.smtp_timeout_s,
        ) as smtp:
            if self._settings.smtp_starttls:
                smtp.starttls()
            if self._settings.smtp_user:
                smtp.login(self._settings.smtp_user, self._settings.smtp_password)
            smtp.send_message(message)
