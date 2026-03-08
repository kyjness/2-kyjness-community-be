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
    # FastAPI의 Swagger UI(/docs)와 ReDoc(/redoc)은 HTML 내 인라인 스크립트를 사용합니다.
    # 개발환경에서 CSP가 엄격하면(예: script-src 'self') 문서 페이지가 하얗게 뜨거나 로딩이 막힐 수 있어,
    # DEBUG=True일 때는 문서 경로에 한해 CSP를 적용하지 않습니다.
    is_docs_path = request.url.path in {
        "/openapi.json",
        "/redoc",
        "/docs/oauth2-redirect",
    } or request.url.path.startswith("/docs")
    if settings.CONTENT_SECURITY_POLICY and not (settings.DEBUG and is_docs_path):
        response.headers["Content-Security-Policy"] = settings.CONTENT_SECURITY_POLICY
    return response
