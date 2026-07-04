# 4xx/5xx·슬로우 요청 접근 로그. request_id는 RequestIdFilter가 주입, 나머지는 extra로 구조화.
import logging
import time
from collections.abc import Awaitable, Callable

from starlette.requests import Request
from starlette.responses import Response

from app.core.config import settings
from app.core.middleware.rate_limit import get_client_ip

_access_logger = logging.getLogger("app.access")


async def access_log_middleware(
    request: Request,
    call_next: Callable[[Request], Awaitable[Response]],
) -> Response:
    """요청 시간 측정. 예외/4xx/5xx/슬로우를 구조화 필드(extra)로 기록. DEBUG 시 X-Process-Time 헤더."""
    start = time.perf_counter()
    try:
        response = await call_next(request)
    except Exception:
        duration_ms = (time.perf_counter() - start) * 1000
        _access_logger.exception(
            "unhandled exception",
            extra={
                "method": request.method,
                "path": request.url.path,
                "duration_ms": round(duration_ms, 2),
                "client_ip": get_client_ip(request),
            },
        )
        raise

    duration_ms = (time.perf_counter() - start) * 1000
    client_ip = get_client_ip(request)

    if settings.DEBUG:
        response.headers["X-Process-Time"] = f"{duration_ms:.2f}"

    fields: dict[str, object] = {
        "method": request.method,
        "path": request.url.path,
        "status": response.status_code,
        "duration_ms": round(duration_ms, 2),
        "client_ip": client_ip,
    }
    if response.status_code >= 500:
        _access_logger.error("access", extra=fields)
    elif response.status_code >= 400:
        _access_logger.warning("access", extra=fields)

    if duration_ms >= settings.SLOW_REQUEST_MS:
        _access_logger.warning("slow request", extra=fields)

    return response
