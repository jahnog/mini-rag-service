from __future__ import annotations

from dataclasses import dataclass, field

from bcra_rag.auth.mail_copy import OTP_SUBJECT, otp_body


@dataclass
class SentMail:
    to: str
    subject: str
    body: str


@dataclass
class FakeMailer:
    sent: list[SentMail] = field(default_factory=list)
    configured: bool = True
    ttl_s: int = 300

    def send_otp(self, *, to: str, code: str) -> None:
        self.sent.append(
            SentMail(to=to, subject=OTP_SUBJECT, body=otp_body(code, ttl_s=self.ttl_s))
        )
