import logging
import time
from datetime import datetime
from typing import Optional

from fastapi import Request
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)


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
    """전역 공통 정책 미들웨어.

    - 전역 Rate Limiting (가능한 빨리 차단)
    - 요청 처리 시간 측정 (X-Process-Time 헤더)
    """
    start_time = time.perf_counter()

    # 문서/헬스체크/정적 리소스 등은 전역 Rate Limiting 대상에서 제외
    path = request.url.path
    skip_prefixes = ("/docs", "/redoc", "/openapi.json", "/public")
    skip_exact = {"/", "/health"}

    if path not in skip_exact and not path.startswith(skip_prefixes):
        # 로컬 개발/학습용: 간단히 IP 기반으로 제한
        # (리버스 프록시 환경이면 X-Forwarded-For를 고려해야 함)
        client_ip = request.client.host if request.client else "unknown"

        # 순환 import 방지용 지연 import
        from app.auth.auth_model import AuthModel

        if not AuthModel.check_rate_limit(client_ip):
            logger.warning("Rate limit exceeded: IP=%s, Path=%s", client_ip, path)
            response = JSONResponse(
                status_code=429,
                content={"code": "RATE_LIMIT_EXCEEDED", "data": None},
            )
            response.headers["X-Process-Time"] = str(time.perf_counter() - start_time)
            return response

    response = await call_next(request)
    response.headers["X-Process-Time"] = str(time.perf_counter() - start_time)
    return response

