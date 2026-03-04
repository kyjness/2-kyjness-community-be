# 4xx/5xx·슬로우 요청 접근 로그. request_id, Method, Path, Status, 소요 시간. 4xx→WARNING, 5xx→ERROR.
import logging
import time
from typing import Awaitable, Callable

from starlette.requests import Request
from starlette.responses import Response

from app.core.config import settings
from app.core.middleware.rate_limit import get_client_ip

_access_logger = logging.getLogger("app.access")


async def access_log_middleware(
    request: Request,
    call_next: Callable[[Request], Awaitable[Response]],
) -> Response:
    """요청 전 구간 시간 측정, call_next 실행. 예외 시 traceback 포함 ERROR 로그 후 재발생. DEBUG 시 X-Process-Time 헤더."""
    start = time.perf_counter()
    try:
        response = await call_next(request)
    except Exception as exc:
        duration_ms = (time.perf_counter() - start) * 1000
        request_id = getattr(request.state, "request_id", "")
        client_ip = get_client_ip(request)
        _access_logger.exception(
            "request_id=%s method=%s path=%s duration_ms=%.2f client_ip=%s exception=%s",
            request_id,
            request.method,
            request.url.path,
            duration_ms,
            client_ip,
            exc,
        )
        raise

    duration_ms = (time.perf_counter() - start) * 1000
    request_id = getattr(request.state, "request_id", "")
    client_ip = get_client_ip(request)

    if settings.DEBUG:
        response.headers["X-Process-Time"] = f"{duration_ms:.2f}"

    if response.status_code >= 500:
        _access_logger.error(
            "request_id=%s method=%s path=%s status=%s duration_ms=%.2f client_ip=%s",
            request_id,
            request.method,
            request.url.path,
            response.status_code,
            duration_ms,
            client_ip,
        )
    elif response.status_code >= 400:
        _access_logger.warning(
            "request_id=%s method=%s path=%s status=%s duration_ms=%.2f client_ip=%s",
            request_id,
            request.method,
            request.url.path,
            response.status_code,
            duration_ms,
            client_ip,
        )

    if duration_ms >= settings.SLOW_REQUEST_MS:
        _access_logger.warning(
            "slow request_id=%s method=%s path=%s status=%s duration_ms=%.2f client_ip=%s",
            request_id,
            request.method,
            request.url.path,
            response.status_code,
            duration_ms,
            client_ip,
        )

    return response
