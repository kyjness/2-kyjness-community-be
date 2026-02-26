from starlette.requests import Request

from app.core.config import settings


async def security_headers_middleware(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = settings.REFERRER_POLICY
    response.headers["Permissions-Policy"] = settings.PERMISSIONS_POLICY
    if settings.HSTS_ENABLED:
        response.headers["Strict-Transport-Security"] = f"max-age={settings.HSTS_MAX_AGE}; includeSubDomains"
    return response
