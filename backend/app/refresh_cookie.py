"""Deliver refresh tokens in an httpOnly cookie instead of the response body.

A refresh token in localStorage can be read by any script that ever runs on
the page, so one script-injection bug would hand out long-lived sessions. The
web app opts in with ``X-Auth-Refresh-Mode: cookie``; for those requests the
refresh token is set as an ``HttpOnly; SameSite=Strict`` cookie scoped to
``/v1/auth`` and left out of the JSON (``refresh_in_cookie: true`` says so).
``/v1/auth/refresh`` then reads it from the cookie.

Clients that don't send the header (API scripts, the test suite, older
browser tabs mid-upgrade) keep receiving the token in the body.
"""
from __future__ import annotations

from typing import TypeVar

from fastapi import Request, Response

from .config import settings

REFRESH_COOKIE_NAME = "ms_refresh"
REFRESH_COOKIE_PATH = "/v1/auth"
MODE_HEADER = "x-auth-refresh-mode"
REMEMBER_HEADER = "x-auth-remember"

T = TypeVar("T")


def wants_refresh_cookie(request: Request | None) -> bool:
    if request is None:
        return False
    return (request.headers.get(MODE_HEADER) or "").strip().lower() == "cookie"


def _secure(request: Request) -> bool:
    if settings.app_env.lower() == "production":
        return True
    forwarded = (request.headers.get("x-forwarded-proto") or "").split(",")[0].strip().lower()
    return request.url.scheme == "https" or forwarded == "https"


def set_refresh_cookie(request: Request, response: Response, token: str, max_age: int | None) -> None:
    # "Remember me" off → a browser-session cookie (gone when the browser closes),
    # matching the old sessionStorage behaviour.
    remember = (request.headers.get(REMEMBER_HEADER) or "1").strip() != "0"
    response.set_cookie(
        REFRESH_COOKIE_NAME,
        token,
        max_age=max_age if (remember and max_age) else None,
        path=REFRESH_COOKIE_PATH,
        httponly=True,
        secure=_secure(request),
        samesite="strict",
    )


def clear_refresh_cookie(request: Request, response: Response) -> None:
    response.delete_cookie(
        REFRESH_COOKIE_NAME,
        path=REFRESH_COOKIE_PATH,
        httponly=True,
        secure=_secure(request),
        samesite="strict",
    )


def presented_refresh_token(request: Request, body_token: str | None) -> str | None:
    """Body token wins (legacy clients); otherwise the cookie."""
    token = (body_token or "").strip()
    if token:
        return token
    cookie = (request.cookies.get(REFRESH_COOKIE_NAME) or "").strip()
    return cookie or None


def deliver_tokens(request: Request, response: Response, body: T) -> T:
    """Move ``body.refresh_token`` into the cookie when the client asked for that."""
    token = getattr(body, "refresh_token", None)
    if not token or not wants_refresh_cookie(request):
        return body
    set_refresh_cookie(request, response, token, getattr(body, "refresh_expires_in_seconds", None))
    body.refresh_token = None
    if hasattr(body, "refresh_in_cookie"):
        body.refresh_in_cookie = True
    return body
