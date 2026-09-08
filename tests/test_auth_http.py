from __future__ import annotations

import re
from pathlib import Path

from fastapi.testclient import TestClient

from bcra_rag.adapters.llm_fake import FakeLlm
from bcra_rag.adapters.session_memory import InMemorySessionStore
from bcra_rag.auth import AuthModule, AuthService, AuthSettings, FakeMailer, build_auth
from bcra_rag.composition import build_app
from tests.chat_fixtures import IN_CORPUS_DRAFT, seed_ready
from tests.test_auth import Clock

SECRET = "s" * 32
OPS = "ops@example.com"


def _client(
    tmp_path: Path,
    *,
    mailer: FakeMailer | None = None,
    auth_settings: AuthSettings | None = None,
) -> tuple[TestClient, FakeMailer]:
    settings, index, _ = seed_ready(tmp_path)
    resolved_mailer = mailer or FakeMailer()
    resolved_auth = build_auth(
        settings=auth_settings
        or AuthSettings(secret=SECRET, allowed_emails=OPS),
        mailer=resolved_mailer,
    )
    app = build_app(
        settings,
        index=index,
        llm=FakeLlm(IN_CORPUS_DRAFT),
        sessions=InMemorySessionStore(),
        auth=resolved_auth,
    )
    return TestClient(app.fastapi), resolved_mailer


def _code(mailer: FakeMailer) -> str:
    match = re.search(r"\b(\d{6})\b", mailer.sent[-1].body)
    assert match
    return match.group(1)


def test_request_and_verify_sets_httponly_cookie(tmp_path: Path) -> None:
    client, mailer = _client(tmp_path)
    requested = client.post("/auth/request", json={"email": OPS})
    assert requested.status_code == 200
    assert requested.json() == {"ok": True}
    verified = client.post("/auth/verify", json={"email": OPS, "code": _code(mailer)})
    assert verified.status_code == 200
    header = verified.headers.get("set-cookie") or ""
    assert "HttpOnly" in header
    assert "samesite=lax" in header.lower()
    assert "max-age=604800" in header.lower()
    me = client.get("/auth/me")
    assert me.status_code == 200
    assert me.json() == {"authenticated": True, "email": OPS}


def test_allowlist_miss_200_and_no_send(tmp_path: Path) -> None:
    client, mailer = _client(tmp_path)
    response = client.post("/auth/request", json={"email": "stranger@example.com"})
    assert response.status_code == 200
    assert response.json() == {"ok": True}
    assert mailer.sent == []


def test_second_request_while_otp_live_coalesces(tmp_path: Path) -> None:
    client, mailer = _client(tmp_path)
    first = client.post("/auth/request", json={"email": OPS})
    second = client.post("/auth/request", json={"email": OPS})
    assert first.status_code == second.status_code == 200
    assert len(mailer.sent) == 1
    verified = client.post("/auth/verify", json={"email": OPS, "code": _code(mailer)})
    assert verified.status_code == 200


def test_second_send_after_short_ttl_is_429(tmp_path: Path) -> None:
    settings, index, _ = seed_ready(tmp_path)
    clock = Clock()
    mailer = FakeMailer()
    auth_settings = AuthSettings(secret=SECRET, allowed_emails=OPS, otp_ttl_s=5)
    service = AuthService(auth_settings, mailer, time_fn=clock)
    auth = AuthModule(settings=auth_settings, service=service, mailer=mailer)
    app = build_app(
        settings,
        index=index,
        llm=FakeLlm(IN_CORPUS_DRAFT),
        sessions=InMemorySessionStore(),
        auth=auth,
    )
    client = TestClient(app.fastapi)
    client.post("/auth/request", json={"email": OPS})
    clock.advance(6)
    denied = client.post("/auth/request", json={"email": OPS})
    assert denied.status_code == 429
    assert denied.headers.get("retry-after")
    assert len(mailer.sent) == 1


def test_origin_mismatch_rejects_without_send(tmp_path: Path) -> None:
    mailer = FakeMailer()
    client, _ = _client(
        tmp_path,
        mailer=mailer,
        auth_settings=AuthSettings(
            secret=SECRET,
            allowed_emails=OPS,
            public_origin="https://rag.example",
        ),
    )
    denied = client.post(
        "/auth/request",
        json={"email": OPS},
        headers={"origin": "https://evil.example"},
    )
    assert denied.status_code == 403
    assert mailer.sent == []


def test_me_unauthenticated_is_200(tmp_path: Path) -> None:
    client, _ = _client(tmp_path)
    response = client.get("/auth/me")
    assert response.status_code == 200
    assert response.json() == {"authenticated": False}


def test_logout_then_me_false(tmp_path: Path) -> None:
    client, mailer = _client(tmp_path)
    client.post("/auth/request", json={"email": OPS})
    client.post("/auth/verify", json={"email": OPS, "code": _code(mailer)})
    logged_out = client.post("/auth/logout")
    assert logged_out.status_code == 200
    me = client.get("/auth/me")
    assert me.json() == {"authenticated": False}


def test_missing_secret_is_503(tmp_path: Path) -> None:
    client, mailer = _client(
        tmp_path,
        auth_settings=AuthSettings(allowed_emails=OPS, secret="short"),
    )
    response = client.post("/auth/request", json={"email": OPS})
    assert response.status_code == 503
    assert mailer.sent == []


def _cookie_header(response) -> str:
    return (response.headers.get("set-cookie") or "").lower()


def test_verify_sets_secure_cookie_when_public_origin_is_https(tmp_path: Path) -> None:
    client, mailer = _client(
        tmp_path,
        auth_settings=AuthSettings(
            secret=SECRET, allowed_emails=OPS, public_origin="https://rag.example"
        ),
    )
    client.post(
        "/auth/request",
        json={"email": OPS},
        headers={"origin": "https://rag.example"},
    )
    verified = client.post(
        "/auth/verify",
        json={"email": OPS, "code": _code(mailer)},
        headers={"origin": "https://rag.example"},
    )
    header = _cookie_header(verified)
    assert "httponly" in header
    assert "samesite=lax" in header
    assert "secure" in header


def test_verify_sets_secure_cookie_when_origin_is_https(tmp_path: Path) -> None:
    client, mailer = _client(tmp_path)
    client.post("/auth/request", json={"email": OPS})
    verified = client.post(
        "/auth/verify",
        json={"email": OPS, "code": _code(mailer)},
        headers={"origin": "https://rag.example"},
    )
    assert "secure" in _cookie_header(verified)


def test_logout_clears_secure_cookie_when_origin_is_https(tmp_path: Path) -> None:
    client, mailer = _client(tmp_path)
    client.post("/auth/request", json={"email": OPS})
    client.post(
        "/auth/verify",
        json={"email": OPS, "code": _code(mailer)},
        headers={"origin": "https://rag.example"},
    )
    logged_out = client.post(
        "/auth/logout", headers={"origin": "https://rag.example"}
    )
    assert "secure" in _cookie_header(logged_out)


def test_verify_cookie_not_secure_on_local_http(tmp_path: Path) -> None:
    client, mailer = _client(tmp_path)
    client.post("/auth/request", json={"email": OPS})
    verified = client.post("/auth/verify", json={"email": OPS, "code": _code(mailer)})
    header = _cookie_header(verified)
    assert "httponly" in header
    assert "secure" not in header


def test_verify_sets_secure_cookie_from_forwarded_proto_when_trust_proxy(
    tmp_path: Path,
) -> None:
    client, mailer = _client(
        tmp_path,
        auth_settings=AuthSettings(
            secret=SECRET, allowed_emails=OPS, trust_proxy=True
        ),
    )
    client.post("/auth/request", json={"email": OPS})
    verified = client.post(
        "/auth/verify",
        json={"email": OPS, "code": _code(mailer)},
        headers={"x-forwarded-proto": "https"},
    )
    assert "secure" in _cookie_header(verified)


def test_forwarded_proto_ignored_without_trust_proxy(tmp_path: Path) -> None:
    client, mailer = _client(tmp_path)
    client.post("/auth/request", json={"email": OPS})
    verified = client.post(
        "/auth/verify",
        json={"email": OPS, "code": _code(mailer)},
        headers={"x-forwarded-proto": "https"},
    )
    assert "secure" not in _cookie_header(verified)


def test_origin_http_rejected_when_public_origin_is_https(tmp_path: Path) -> None:
    mailer = FakeMailer()
    client, _ = _client(
        tmp_path,
        mailer=mailer,
        auth_settings=AuthSettings(
            secret=SECRET,
            allowed_emails=OPS,
            public_origin="https://rag.example",
        ),
    )
    denied = client.post(
        "/auth/request",
        json={"email": OPS},
        headers={"origin": "http://rag.example"},
    )
    assert denied.status_code == 403
    assert mailer.sent == []
    verify = client.post(
        "/auth/verify",
        json={"email": OPS, "code": "000000"},
        headers={"origin": "http://rag.example"},
    )
    assert verify.status_code == 403


def test_origin_port_mismatch_rejected(tmp_path: Path) -> None:
    mailer = FakeMailer()
    client, _ = _client(
        tmp_path,
        mailer=mailer,
        auth_settings=AuthSettings(
            secret=SECRET,
            allowed_emails=OPS,
            public_origin="https://rag.example:8443",
        ),
    )
    denied = client.post(
        "/auth/request",
        json={"email": OPS},
        headers={"origin": "https://rag.example"},
    )
    assert denied.status_code == 403
    assert mailer.sent == []


def test_origin_https_default_port_matches(tmp_path: Path) -> None:
    mailer = FakeMailer()
    client, _ = _client(
        tmp_path,
        mailer=mailer,
        auth_settings=AuthSettings(
            secret=SECRET,
            allowed_emails=OPS,
            public_origin="https://rag.example",
        ),
    )
    ok = client.post(
        "/auth/request",
        json={"email": OPS},
        headers={"origin": "https://rag.example:443"},
    )
    assert ok.status_code == 200
    assert mailer.sent


def test_smtp_failure_is_503_without_mailbox(tmp_path: Path) -> None:
    class Boom:
        configured = True

        def send_otp(self, *, to: str, code: str) -> None:
            raise RuntimeError("down")

    client, _ = _client(tmp_path, mailer=Boom())  # type: ignore[arg-type]
    response = client.post("/auth/request", json={"email": OPS})
    assert response.status_code == 503
    body = str(response.json())
    assert OPS not in body
    assert "down" not in body.lower()
