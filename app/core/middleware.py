"""
전역 미들웨어.
- Rate Limiting: RATE_LIMIT_ENABLED일 때만 적용 (로컬/DEV는 비활성화 권장)
- Process-Time: DEBUG일 때만 헤더 추가
- 로깅: 500ms 이상일 때만 info, 그 외 debug
- 보안 헤더: 최소 세트만 (X-Frame-Options, X-Content-Type-Options). CSP/HSTS는 로컬·과제 환경 제외
"""

import logging
import time
from datetime import datetime
from typing import Dict, Optional

from fastapi import Request
from fastapi.responses import JSONResponse

from app.core.config import settings

logger = logging.getLogger(__name__)

# Rate limiting 저장소 (미들웨어에서만 관리)
_rate_limits: Dict[str, dict] = {}

# 보안 헤더 최소 세트 (로컬·과제 환경에 적합. PROD 배포 시 CSP/HSTS 등 추가 가능)
MINIMAL_SECURITY_HEADERS = {
    "X-Frame-Options": "DENY",
    "X-Content-Type-Options": "nosniff",
}

# 500ms 이상일 때만 info 로그 (그 외는 debug)
SLOW_REQUEST_MS = 500


def _check_rate_limit(client_ip: str) -> bool:
    """True: 허용, False: 거부. RATE_LIMIT_ENABLED일 때만 의미 있음."""
    current_time = time.time()
    window = settings.RATE_LIMIT_WINDOW
    max_requests = settings.RATE_LIMIT_MAX_REQUESTS

    if client_ip not in _rate_limits:
        _rate_limits[client_ip] = {"requests": [], "window_start": current_time}

    rate_info = _rate_limits[client_ip]
    rate_info["requests"] = [
        t for t in rate_info["requests"]
        if current_time - t < window
    ]

    if len(rate_info["requests"]) >= max_requests:
        return False
    rate_info["requests"].append(current_time)
    return True


async def security_headers_middleware(request: Request, call_next):
    """최소 보안 헤더만 추가 (CSP/HSTS 제외)."""
    response = await call_next(request)
    for key, value in MINIMAL_SECURITY_HEADERS.items():
        response.headers[key] = value
    return response


def _console_sql_log(method: str, path: str, sql: Optional[str]) -> None:
    """콘솔에 요청 시각과 SQL 문을 함께 출력."""
    if not sql:
        return
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] {method} {path}\n    SQL: {sql}"
    print(line, flush=True)


async def sql_logging_middleware(request: Request, call_next):
    """API 요청 시 콘솔에 요청 시각과 해당 요청에 대응하는 SQL 문을 함께 출력."""
    method = request.method
    path = request.url.path or ""
    sql = None
    try:
        from app.core.database import sql_for_request
        sql = sql_for_request(method, path)
    except Exception:
        pass
    _console_sql_log(method, path, sql)
    response = await call_next(request)
    return response


async def global_policy_middleware(request: Request, call_next):
    """
    - Rate Limiting: RATE_LIMIT_ENABLED일 때만 적용
    - X-Process-Time: DEBUG일 때만 헤더 추가
    - 로깅: 500ms 이상이면 info, 아니면 debug
    """
    start_time = time.perf_counter()
    path = request.url.path
    skip_prefixes = ("/docs", "/redoc", "/openapi.json", "/public")
    skip_exact = {"/", "/health"}

    # Rate Limit (환경 토글)
    if settings.RATE_LIMIT_ENABLED and path not in skip_exact and not path.startswith(skip_prefixes):
        client_ip = request.client.host if request.client else "unknown"
        if not _check_rate_limit(client_ip):
            duration_ms = (time.perf_counter() - start_time) * 1000
            logger.warning(
                "Rate limit exceeded: IP=%s, Path=%s, duration_ms=%.2f",
                client_ip, path, duration_ms,
            )
            response = JSONResponse(
                status_code=429,
                content={"code": "RATE_LIMIT_EXCEEDED", "data": None},
            )
            if settings.DEBUG:
                response.headers["X-Process-Time"] = str(duration_ms / 1000)
            return response

    response = await call_next(request)
    duration_ms = (time.perf_counter() - start_time) * 1000

    if settings.DEBUG:
        response.headers["X-Process-Time"] = str(duration_ms / 1000)

    if duration_ms >= SLOW_REQUEST_MS:
        logger.info(
            "Request completed: path=%s, status=%s, duration_ms=%.2f",
            path, response.status_code, duration_ms,
        )
    else:
        logger.debug(
            "Request completed: path=%s, status=%s, duration_ms=%.2f",
            path, response.status_code, duration_ms,
        )

    return response
