"""HTTP authentication routes for backend-issued session cookies."""

from __future__ import annotations

import asyncio

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from . import auth as auth_utils
from .settings import settings

router = APIRouter(prefix="/api/auth", tags=["auth"])


class LoginRequest(BaseModel):
    email: str | None = None
    password: str | None = None


class AuthUserResponse(BaseModel):
    uid: str
    email: str | None = None
    is_anonymous: bool = False


def _cookie_domain() -> str | None:
    domain = settings.session_cookie_domain.strip()
    return domain or None


def _set_auth_cookie(response: JSONResponse, session_cookie: str) -> None:
    response.set_cookie(
        key=settings.session_cookie_name,
        value=session_cookie,
        max_age=max(300, settings.session_cookie_max_age_seconds),
        httponly=True,
        secure=settings.session_cookie_secure,
        samesite=settings.session_cookie_samesite,
        path="/",
        domain=_cookie_domain(),
    )


def _clear_auth_cookie(response: JSONResponse) -> None:
    response.delete_cookie(
        key=settings.session_cookie_name,
        path="/",
        domain=_cookie_domain(),
    )


@router.post("/login", response_model=AuthUserResponse)
async def login(payload: LoginRequest) -> JSONResponse:
    """Authenticate with Firebase and issue a secure HTTP-only session cookie."""
    email = (payload.email or "").strip()
    password = (payload.password or "").strip()
    if email and not password:
        raise HTTPException(status_code=400, detail="Password is required when email is provided")
    if password and not email:
        raise HTTPException(status_code=400, detail="Email is required when password is provided")

    if email:
        id_token = await asyncio.to_thread(auth_utils.sign_in_with_email_password, email, password)
    else:
        id_token = await asyncio.to_thread(auth_utils.sign_in_anonymously)

    claims = await asyncio.to_thread(auth_utils.verify_firebase_token, id_token)
    session_cookie = await asyncio.to_thread(auth_utils.create_firebase_session_cookie, id_token)
    payload = AuthUserResponse(
        uid=str(claims.get("uid", "")),
        email=claims.get("email"),
        is_anonymous=bool(claims.get("firebase", {}).get("sign_in_provider") == "anonymous"),
    )
    response = JSONResponse(payload.model_dump())
    _set_auth_cookie(response, session_cookie)
    return response


@router.post("/logout")
async def logout() -> JSONResponse:
    """Clear the auth cookie."""
    response = JSONResponse({"ok": True})
    _clear_auth_cookie(response)
    return response


@router.get("/me", response_model=AuthUserResponse)
async def me(current_user: dict = Depends(auth_utils.get_current_user)) -> AuthUserResponse:
    """Return the currently authenticated user."""
    return AuthUserResponse(
        uid=str(current_user.get("uid", "")),
        email=current_user.get("email"),
        is_anonymous=bool(current_user.get("firebase", {}).get("sign_in_provider") == "anonymous"),
    )

