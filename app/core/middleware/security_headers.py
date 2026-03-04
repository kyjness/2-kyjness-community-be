# 보안 헤더. X-Frame-Options, X-Content-Type-Options, Referrer-Policy, Permissions-Policy, CSP.
from typing import Awaitable, Callable

from starlette.requests import Request
from starlette.responses import Response

from app.core.config import settings


async def security_headers_middleware(
    request: Request,
    call_next: Callable[[Request], Awaitable[Response]],
) -> Response:
    response = await call_next(request)
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = settings.REFERRER_POLICY
    response.headers["Permissions-Policy"] = settings.PERMISSIONS_POLICY
    if settings.HSTS_ENABLED:
        response.headers["Strict-Transport-Security"] = (
            f"max-age={settings.HSTS_MAX_AGE}; includeSubDomains"
        )
    if settings.CONTENT_SECURITY_POLICY:
        response.headers["Content-Security-Policy"] = settings.CONTENT_SECURITY_POLICY
    return response
