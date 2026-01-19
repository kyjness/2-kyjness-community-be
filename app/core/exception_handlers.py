import logging

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)


def register_exception_handlers(app: FastAPI) -> None:
    """전역 예외 핸들러 등록."""

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError):
        # 요청 바디/쿼리/패스 파라미터 검증 오류
        logger.warning(
            "Validation error: Path=%s, Errors=%s",
            request.url.path,
            exc.errors(),
        )
        return JSONResponse(
            status_code=400,
            content={"code": "INVALID_REQUEST_BODY", "data": None},
        )

    @app.exception_handler(HTTPException)
    async def http_exception_handler(request: Request, exc: HTTPException):
        # 보안 관련(401/403)은 WARNING, 그 외 4xx는 INFO
        if exc.status_code in (401, 403):
            logger.warning(
                "Security error: Status=%s, Path=%s, Detail=%s",
                exc.status_code,
                request.url.path,
                exc.detail,
            )
        elif 400 <= exc.status_code < 500:
            logger.info(
                "Client error: Status=%s, Path=%s, Detail=%s",
                exc.status_code,
                request.url.path,
                exc.detail,
            )

        # HTTP 상태 코드는 유지, 응답 포맷만 통일
        if isinstance(exc.detail, dict):
            return JSONResponse(status_code=exc.status_code, content=exc.detail)
        return JSONResponse(
            status_code=exc.status_code,
            content={"code": str(exc.detail) if exc.detail else "HTTP_ERROR", "data": None},
        )

    @app.exception_handler(Exception)
    async def general_exception_handler(request: Request, exc: Exception):
        logger.error(
            "Unhandled exception: Path=%s, Exception=%s: %s",
            request.url.path,
            type(exc).__name__,
            str(exc),
            exc_info=True,
        )
        return JSONResponse(
            status_code=500,
            content={"code": "INTERNAL_SERVER_ERROR", "data": None},
        )

