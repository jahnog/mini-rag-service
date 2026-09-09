from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Request, Response
from fastapi.responses import HTMLResponse, RedirectResponse
from pydantic import BaseModel, Field

from bcra_rag.auth import AuthModule, AuthRejected, AuthUnavailable, email_from_request
from bcra_rag.auth.cookies import (
    INTENT_COOKIE,
    LINK_COOKIE,
    LINK_COOKIE_PATH,
)
from bcra_rag.auth.ip import client_ip
from bcra_rag.auth.origin import cookie_secure, origin_matches
from bcra_rag.auth.pages import confirm_page, fail_page

_LINK_CSP = (
    "default-src 'none'; form-action 'self'; base-uri 'none'; "
    "frame-ancestors 'none'; style-src 'unsafe-inline'"
)


class EmailBody(BaseModel):
    email: str = Field(min_length=1)


class VerifyBody(BaseModel):
    email: str = Field(min_length=1)
    code: str = Field(min_length=1)


def build_router(auth: AuthModule) -> APIRouter:
    router = APIRouter()

    @router.post("/auth/request")
    def request_otp(payload: EmailBody, request: Request, response: Response) -> dict[str, bool]:
        _reject_bad_origin(request, auth)
        _require_secret(auth)
        try:
            issued = auth.service.request_otp(payload.email, _ip(auth, request))
        except AuthUnavailable:
            raise HTTPException(status_code=503, detail="authentication unavailable")
        except AuthRejected as exc:
            _raise_rejected(exc)
        if issued.intent_nonce:
            _set_link_cookie(
                auth,
                request,
                response,
                INTENT_COOKIE,
                issued.intent_nonce,
                max_age=auth.settings.otp_ttl_s,
            )
        return {"ok": True}

    @router.post("/auth/verify")
    def verify_otp(payload: VerifyBody, request: Request, response: Response) -> dict[str, bool]:
        _reject_bad_origin(request, auth)
        _require_secret(auth)
        try:
            cookie = auth.service.verify_otp(payload.email, payload.code, _ip(auth, request))
        except AuthUnavailable:
            raise HTTPException(status_code=503, detail="authentication unavailable")
        except AuthRejected as exc:
            _raise_rejected(exc)
        _set_session_cookie(auth, request, response, cookie)
        _clear_link_cookies(auth, request, response)
        return {"ok": True}

    @router.api_route("/auth/link/{token}", methods=["GET", "HEAD"])
    def wash_link(token: str, request: Request) -> Response:
        _require_secret(auth)
        if request.method == "HEAD":
            response = Response(status_code=200)
            _apply_link_headers(response)
            return response
        response = RedirectResponse(url="/auth/link", status_code=302)
        _apply_link_headers(response)
        _set_link_cookie(
            auth,
            request,
            response,
            LINK_COOKIE,
            token,
            max_age=auth.settings.otp_ttl_s,
        )
        return response

    @router.api_route("/auth/link", methods=["GET", "HEAD", "POST"])
    def consume_link(request: Request) -> Response:
        _require_secret(auth)
        if request.method == "HEAD":
            response = Response(status_code=200)
            _apply_link_headers(response)
            return response
        if request.method == "POST":
            try:
                _reject_bad_origin(request, auth)
            except HTTPException:
                auth.service.note_consume_fail(_ip(auth, request))
                raise
            return _finish_consume(auth, request)
        token = request.cookies.get(LINK_COOKIE) or ""
        intent = request.cookies.get(INTENT_COOKIE) or ""
        email = auth.service.inspect_link(token)
        if email is None:
            return _fail_html()
        navigate = (
            request.headers.get("sec-fetch-mode") == "navigate"
            and request.headers.get("sec-fetch-dest") == "document"
        )
        if navigate and auth.service.intent_matches(token, intent):
            return _finish_consume(auth, request)
        response = HTMLResponse(confirm_page(email))
        _apply_link_headers(response)
        return response

    @router.post("/auth/logout")
    def logout(request: Request, response: Response) -> dict[str, bool]:
        response.delete_cookie(
            auth.settings.cookie_name,
            path="/",
            httponly=True,
            samesite="lax",
            secure=cookie_secure(request, auth.settings),
        )
        _clear_link_cookies(auth, request, response)
        return {"ok": True}

    @router.get("/auth/me")
    def me(request: Request) -> dict[str, Any]:
        email = email_from_request(auth, request)
        if email is None:
            return {"authenticated": False}
        return {"authenticated": True, "email": email}

    return router


def _finish_consume(auth: AuthModule, request: Request) -> Response:
    token = request.cookies.get(LINK_COOKIE) or ""
    try:
        cookie = auth.service.consume_link(token, _ip(auth, request))
    except AuthUnavailable:
        raise HTTPException(status_code=503, detail="authentication unavailable")
    except AuthRejected as exc:
        if exc.status == 429:
            _raise_rejected(exc)
        return _fail_html()
    response = RedirectResponse(url="/", status_code=302)
    _apply_link_headers(response)
    _set_session_cookie(auth, request, response, cookie)
    _clear_link_cookies(auth, request, response)
    return response


def _fail_html() -> HTMLResponse:
    response = HTMLResponse(fail_page())
    _apply_link_headers(response)
    return response


def _apply_link_headers(response: Response) -> None:
    response.headers["Cache-Control"] = "no-store"
    response.headers["Pragma"] = "no-cache"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Content-Security-Policy"] = _LINK_CSP


def _set_link_cookie(
    auth: AuthModule,
    request: Request,
    response: Response,
    name: str,
    value: str,
    *,
    max_age: int,
) -> None:
    response.set_cookie(
        key=name,
        value=value,
        max_age=max_age,
        httponly=True,
        samesite="lax",
        path=LINK_COOKIE_PATH,
        secure=cookie_secure(request, auth.settings),
    )


def _clear_link_cookies(auth: AuthModule, request: Request, response: Response) -> None:
    secure = cookie_secure(request, auth.settings)
    for name in (INTENT_COOKIE, LINK_COOKIE):
        response.delete_cookie(
            name,
            path=LINK_COOKIE_PATH,
            httponly=True,
            samesite="lax",
            secure=secure,
        )


def _ip(auth: AuthModule, request: Request) -> str:
    return client_ip(request, trusted_proxy=auth.settings.trust_proxy)


def _require_secret(auth: AuthModule) -> None:
    if not auth.settings.secret_ok:
        raise HTTPException(status_code=503, detail="authentication unavailable")


def _reject_bad_origin(request: Request, auth: AuthModule) -> None:
    expected = auth.settings.public_origin.strip()
    if not expected:
        return
    incoming = request.headers.get("origin") or request.headers.get("referer") or ""
    if not origin_matches(expected, incoming):
        raise HTTPException(status_code=403, detail="invalid origin")


def _set_session_cookie(
    auth: AuthModule, request: Request, response: Response, value: str
) -> None:
    response.set_cookie(
        key=auth.settings.cookie_name,
        value=value,
        max_age=auth.settings.session_ttl_s,
        httponly=True,
        samesite="lax",
        path="/",
        secure=cookie_secure(request, auth.settings),
    )


def _raise_rejected(exc: AuthRejected) -> None:
    headers = {}
    if exc.retry_after is not None:
        headers["Retry-After"] = str(exc.retry_after)
    raise HTTPException(status_code=exc.status, detail=exc.detail, headers=headers or None)
