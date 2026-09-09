from __future__ import annotations

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

SECRET_MIN_LEN = 32


class AuthSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="AUTH_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Secret / allowlist
    secret: str = ""
    allowed_emails: str = ""

    # Session cookie
    cookie_name: str = "session"
    session_days: int = Field(default=1, ge=1)

    # OTP
    otp_ttl_s: int = Field(default=300, ge=1)
    otp_digits: int = Field(default=6, ge=4, le=8)

    # Request origin
    trust_proxy: bool = False
    public_origin: str = ""

    # SMTP
    smtp_host: str = ""
    smtp_port: int = Field(default=587, ge=1)
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_from: str = ""
    smtp_starttls: bool = True
    smtp_timeout_s: float = Field(default=10.0, ge=0.1)

    # Auth rate limits
    max_distinct_emails_per_ip_day: int = Field(default=5, ge=1)
    max_sends_per_email_minute: int = Field(default=1, ge=1)
    max_sends_per_email_day: int = Field(default=10, ge=1)
    max_sends_per_ip_day: int = Field(default=20, ge=1)
    max_verify_fails_per_otp: int = Field(default=5, ge=1)
    max_verify_fails_per_ip_hour: int = Field(default=15, ge=1)
    verify_ip_cooldown_s: int = Field(default=900, ge=1)
    min_verify_interval_s: float = Field(default=2.0, ge=0.0)
    max_sends_per_process_day: int = Field(default=200, ge=1)

    @property
    def session_ttl_s(self) -> int:
        return self.session_days * 86400

    @property
    def secret_ok(self) -> bool:
        return len(self.secret) >= SECRET_MIN_LEN

    def allowlist(self) -> frozenset[str]:
        return frozenset(
            part.strip().lower()
            for part in self.allowed_emails.split(",")
            if part.strip()
        )
