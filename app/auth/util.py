# app/auth/util.py
"""인증 관련 유틸."""

from starlette.responses import JSONResponse

from app.core.config import settings


def set_cookie(response: JSONResponse, session_id: str) -> None:
    response.set_cookie(
        key="session_id",
        value=session_id,
        httponly=True,
        secure=settings.COOKIE_SECURE,
        path="/",
        samesite="lax",
        max_age=settings.SESSION_EXPIRY_TIME,
    )
