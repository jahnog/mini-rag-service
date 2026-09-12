from __future__ import annotations

import re
from pathlib import Path

from fastapi.testclient import TestClient

from bcra_rag.adapters.llm_fake import FakeLlm
from bcra_rag.adapters.session_memory import InMemorySessionStore
from bcra_rag.auth import (
    AuthModule,
    AuthService,
    AuthSettings,
    FakeMailer,
    build_auth,
    otp_code_from_text,
)
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
        or AuthSettings(_env_file=None, secret=SECRET, allowed_emails=OPS),
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
    assert mailer.sent
    code = otp_code_from_text(mailer.sent[-1].body)
    assert code
    return code


def _token(mailer: FakeMailer) -> str:
    match = re.search(r"/auth/link/([A-Za-z0-9_-]+)", mailer.sent[-1].body)
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
    assert "max-age=86400" in header.lower()
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
    auth_settings = AuthSettings(
        _env_file=None, secret=SECRET, allowed_emails=OPS, otp_ttl_s=5
    )
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
            _env_file=None,
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
        auth_settings=AuthSettings(
            _env_file=None, allowed_emails=OPS, secret="short"
        ),
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
            _env_file=None,
            secret=SECRET,
            allowed_emails=OPS,
            public_origin="https://rag.example",
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
            _env_file=None, secret=SECRET, allowed_emails=OPS, trust_proxy=True
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
            _env_file=None,
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
            _env_file=None,
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
            _env_file=None,
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

        def send_otp(
            self, *, to: str, code: str, login_url: str | None = None
        ) -> None:
            raise RuntimeError("down")

    client, _ = _client(tmp_path, mailer=Boom())  # type: ignore[arg-type]
    response = client.post("/auth/request", json={"email": OPS})
    assert response.status_code == 503
    body = str(response.json())
    assert OPS not in body
    assert "down" not in body.lower()


ORIGIN = "http://testserver"
_NAV = {"sec-fetch-mode": "navigate", "sec-fetch-dest": "document"}


def _link_client(tmp_path: Path) -> tuple[TestClient, FakeMailer]:
    mailer = FakeMailer()
    client, _ = _client(
        tmp_path,
        mailer=mailer,
        auth_settings=AuthSettings(
            _env_file=None,
            secret=SECRET,
            allowed_emails=f"{OPS},other@example.com",
            public_origin=ORIGIN,
        ),
    )
    return client, mailer


def _request_link(client: TestClient, mailer: FakeMailer, email: str = OPS) -> str:
    posted = client.post(
        "/auth/request", json={"email": email}, headers={"origin": ORIGIN}
    )
    assert posted.status_code == 200
    return _token(mailer)


def test_wash_does_not_set_session(tmp_path: Path) -> None:
    client, mailer = _link_client(tmp_path)
    token = _request_link(client, mailer)
    wash = client.get(f"/auth/link/{token}", follow_redirects=False)
    assert wash.status_code == 302
    location = wash.headers.get("location", "")
    assert location.endswith("/auth/link")
    assert token not in location
    cookie_header = wash.headers.get("set-cookie") or ""
    assert "auth_link=" in cookie_header
    assert "session=" not in cookie_header
    assert "httponly" in cookie_header.lower()
    assert "path=/auth/link" in cookie_header.lower()
    assert wash.headers.get("cache-control") == "no-store"
    assert wash.headers.get("referrer-policy") == "no-referrer"
    assert wash.headers.get("x-frame-options") == "DENY"
    assert "frame-ancestors 'none'" in (wash.headers.get("content-security-policy") or "")
    assert client.get("/auth/me").json()["authenticated"] is False
    assert "gradio" not in wash.text.lower()


def test_mail_referer_wash_is_not_403(tmp_path: Path) -> None:
    client, mailer = _link_client(tmp_path)
    token = _request_link(client, mailer)
    wash = client.get(
        f"/auth/link/{token}",
        follow_redirects=False,
        headers={"referer": "https://mail.google.com"},
    )
    assert wash.status_code == 302


def test_scanner_get_does_not_sign_in_or_burn(tmp_path: Path) -> None:
    client, mailer = _link_client(tmp_path)
    token = _request_link(client, mailer)
    code = _code(mailer)
    client.get(f"/auth/link/{token}", follow_redirects=False)
    page = client.get("/auth/link", follow_redirects=False)
    assert page.status_code == 200
    assert "<title>BCRA CAMEX</title>" in page.text
    assert "Iniciar sesión" in page.text
    assert OPS in page.text
    assert token not in page.text
    assert 'method="post"' in page.text.lower()
    assert 'action="/auth/link"' in page.text
    assert client.get("/auth/me").json()["authenticated"] is False
    verified = client.post(
        "/auth/verify",
        json={"email": OPS, "code": code},
        headers={"origin": ORIGIN},
    )
    assert verified.status_code == 200


def test_auto_login_with_intent_and_navigation(tmp_path: Path) -> None:
    client, mailer = _link_client(tmp_path)
    token = _request_link(client, mailer)
    client.get(f"/auth/link/{token}", follow_redirects=False)
    landed = client.get("/auth/link", follow_redirects=False, headers=_NAV)
    assert landed.status_code == 302
    assert landed.headers.get("location", "").endswith("/")
    header = landed.headers.get("set-cookie") or ""
    assert "session=" in header
    assert "max-age=86400" in header.lower()
    assert client.get("/auth/me").json() == {"authenticated": True, "email": OPS}


def test_coalesced_request_still_auto_logins(tmp_path: Path) -> None:
    client, mailer = _link_client(tmp_path)
    token = _request_link(client, mailer)
    again = client.post(
        "/auth/request", json={"email": OPS}, headers={"origin": ORIGIN}
    )
    assert again.status_code == 200
    client.get(f"/auth/link/{token}", follow_redirects=False)
    landed = client.get("/auth/link", follow_redirects=False, headers=_NAV)
    assert landed.status_code == 302
    assert client.get("/auth/me").json()["authenticated"] is True


def test_other_browser_confirm_post(tmp_path: Path) -> None:
    owner, mailer = _link_client(tmp_path)
    token = _request_link(owner, mailer)
    other = TestClient(owner.app)
    other.get(f"/auth/link/{token}", follow_redirects=False)
    page = other.get("/auth/link", follow_redirects=False)
    assert OPS in page.text
    assert token not in page.text
    posted = other.post("/auth/link", follow_redirects=False, headers={"origin": ORIGIN})
    assert posted.status_code == 302
    assert other.get("/auth/me").json()["authenticated"] is True
    assert owner.get("/auth/me").json()["authenticated"] is False


def test_confirm_origin_mismatch_does_not_burn(tmp_path: Path) -> None:
    client, mailer = _link_client(tmp_path)
    token = _request_link(client, mailer)
    client.get(f"/auth/link/{token}", follow_redirects=False)
    denied = client.post(
        "/auth/link", follow_redirects=False, headers={"origin": "https://evil.example"}
    )
    assert denied.status_code == 403
    ok = client.post("/auth/link", follow_redirects=False, headers={"origin": ORIGIN})
    assert ok.status_code == 302
    assert client.get("/auth/me").json()["authenticated"] is True


def test_head_does_not_consume(tmp_path: Path) -> None:
    client, mailer = _link_client(tmp_path)
    token = _request_link(client, mailer)
    headed = client.head(f"/auth/link/{token}")
    assert headed.status_code == 200
    assert "session=" not in (headed.headers.get("set-cookie") or "")
    client.get(f"/auth/link/{token}", follow_redirects=False)
    client.get("/auth/link", follow_redirects=False, headers=_NAV)
    assert client.get("/auth/me").json()["authenticated"] is True


def test_unknown_token_is_generic(tmp_path: Path) -> None:
    client, _ = _link_client(tmp_path)
    wash = client.get("/auth/link/not-a-real-token", follow_redirects=False)
    assert wash.status_code == 302
    page = client.get("/auth/link", follow_redirects=False)
    assert "Este enlace no es válido o venció." in page.text
    assert 'href="/"' in page.text
    assert client.get("/auth/me").json()["authenticated"] is False


def test_failed_consume_does_not_burn_other_mailbox(tmp_path: Path) -> None:
    client, mailer = _link_client(tmp_path)
    _request_link(client, mailer, OPS)
    ops_code = _code(mailer)
    _request_link(client, mailer, "other@example.com")
    other_code = _code(mailer)
    client.post("/auth/link", follow_redirects=False, headers={"origin": ORIGIN})
    assert (
        client.post(
            "/auth/verify",
            json={"email": OPS, "code": ops_code},
            headers={"origin": ORIGIN},
        ).status_code
        == 200
    )
    other = TestClient(client.app)
    assert (
        other.post(
            "/auth/verify",
            json={"email": "other@example.com", "code": other_code},
            headers={"origin": ORIGIN},
        ).status_code
        == 200
    )


def test_intent_cookie_not_sent_to_chat(tmp_path: Path) -> None:
    client, mailer = _link_client(tmp_path)
    _request_link(client, mailer)
    chat = client.post("/chat", json={"message": "Qué es el MULC?"})
    assert chat.status_code == 401


def test_logout_after_link_login(tmp_path: Path) -> None:
    client, mailer = _link_client(tmp_path)
    token = _request_link(client, mailer)
    client.get(f"/auth/link/{token}", follow_redirects=False)
    client.get("/auth/link", follow_redirects=False, headers=_NAV)
    client.post("/auth/logout")
    assert client.get("/auth/me").json() == {"authenticated": False}
    assert client.post("/chat", json={"message": "hola"}).status_code == 401


def test_link_cookies_secure_when_public_origin_https(tmp_path: Path) -> None:
    mailer = FakeMailer()
    client, _ = _client(
        tmp_path,
        mailer=mailer,
        auth_settings=AuthSettings(
            _env_file=None,
            secret=SECRET,
            allowed_emails=OPS,
            public_origin="https://rag.example",
        ),
    )
    requested = client.post(
        "/auth/request",
        json={"email": OPS},
        headers={"origin": "https://rag.example"},
    )
    intent = requested.headers.get("set-cookie") or ""
    assert "secure" in intent.lower()
    token = _token(mailer)
    wash = client.get(f"/auth/link/{token}", follow_redirects=False)
    assert "secure" in (wash.headers.get("set-cookie") or "").lower()

