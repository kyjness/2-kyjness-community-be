import logging
import time

from starlette.requests import Request

from app.core.config import settings
from app.core.middleware.rate_limit import get_client_ip

_access_logger = logging.getLogger("app.access")


async def access_log_middleware(request: Request, call_next):
    start = time.perf_counter()
    response = await call_next(request)
    duration_ms = (time.perf_counter() - start) * 1000
    request_id = getattr(request.state, "request_id", "")
    client_ip = get_client_ip(request)
    if settings.DEBUG:
        response.headers["X-Process-Time"] = f"{duration_ms:.2f}"
    if response.status_code >= 400:
        _access_logger.info(
            "request_id=%s method=%s path=%s status=%s duration_ms=%.2f client_ip=%s",
            request_id, request.method, request.url.path, response.status_code, duration_ms, client_ip,
        )
    slow_ms = settings.SLOW_REQUEST_MS
    if duration_ms >= slow_ms:
        _access_logger.info(
            "slow request_id=%s method=%s path=%s status=%s duration_ms=%.2f client_ip=%s",
            request_id, request.method, request.url.path, response.status_code, duration_ms, client_ip,
        )
    return response
