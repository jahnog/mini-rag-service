from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel, Field

from bcra_rag.auth import AuthModule, AuthRejected, AuthUnavailable, email_from_request
from bcra_rag.auth.ip import client_ip
from bcra_rag.auth.origin import cookie_secure, origin_matches


class EmailBody(BaseModel):
    email: str = Field(min_length=1)


class VerifyBody(BaseModel):
    email: str = Field(min_length=1)
    code: str = Field(min_length=1)


def build_router(auth: AuthModule) -> APIRouter:
    router = APIRouter()

    @router.post("/auth/request")
    def request_otp(payload: EmailBody, request: Request) -> dict[str, bool]:
        _reject_bad_origin(request, auth)
        _require_secret(auth)
        try:
            auth.service.request_otp(payload.email, _ip(auth, request))
        except AuthUnavailable:
            raise HTTPException(status_code=503, detail="authentication unavailable")
        except AuthRejected as exc:
            _raise_rejected(exc)
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
        return {"ok": True}

    @router.post("/auth/logout")
    def logout(request: Request, response: Response) -> dict[str, bool]:
        response.delete_cookie(
            auth.settings.cookie_name,
            path="/",
            httponly=True,
            samesite="lax",
            secure=cookie_secure(request, auth.settings),
        )
        return {"ok": True}

    @router.get("/auth/me")
    def me(request: Request) -> dict[str, Any]:
        email = email_from_request(auth, request)
        if email is None:
            return {"authenticated": False}
        return {"authenticated": True, "email": email}

    return router


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
