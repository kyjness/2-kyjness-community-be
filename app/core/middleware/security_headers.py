# 보안 헤더. X-Frame-Options, X-Content-Type-Options, Referrer-Policy, Permissions-Policy, CSP.
from collections.abc import Awaitable, Callable

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
    # Swagger/ReDoc은 CDN·인라인 스크립트를 쓰므로 엄격한 CSP(self만 허용)와 충돌.
    # 실무: docs 경로는 CSP 미적용(내부/개발용으로 간주). API_PREFIX 기준으로 판별.
    prefix = settings.API_PREFIX.rstrip("/")
    is_docs_path = (
        request.url.path == f"{prefix}/openapi.json"
        or request.url.path == f"{prefix}/redoc"
        or request.url.path == f"{prefix}/docs/oauth2-redirect"
        or request.url.path.startswith(f"{prefix}/docs")
    )
    if settings.CONTENT_SECURITY_POLICY and not is_docs_path:
        response.headers["Content-Security-Policy"] = settings.CONTENT_SECURITY_POLICY
    return response
