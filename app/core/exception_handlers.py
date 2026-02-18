# app/core/exception_handlers.py
"""전역 예외 핸들러. 모든 오류 응답을 { code, data } 형식으로 통일."""

import logging

import pymysql
from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.core.codes import ApiCode

logger = logging.getLogger(__name__)


# 라우트 없음(404), 메서드 불일치(405) 등 공통 code 매핑
HTTP_STATUS_TO_CODE = {
    400: ApiCode.INVALID_REQUEST,
    401: ApiCode.UNAUTHORIZED,
    403: ApiCode.FORBIDDEN,
    404: ApiCode.NOT_FOUND,
    405: ApiCode.METHOD_NOT_ALLOWED,
    409: ApiCode.CONFLICT,
    422: ApiCode.UNPROCESSABLE_ENTITY,
    429: ApiCode.RATE_LIMIT_EXCEEDED,
    500: ApiCode.INTERNAL_SERVER_ERROR,
}


def register_exception_handlers(app: FastAPI) -> None:
    """전역 예외 핸들러 등록. 어떤 예외든 { code, data } 형식으로 응답."""

    # DTO 검증 시 validators.ensure_*가 ValueError("INVALID_XXX")로 던진 코드 보존
    _KNOWN_VALIDATION_CODES = frozenset({
        "INVALID_PASSWORD_FORMAT", "INVALID_NICKNAME_FORMAT", "INVALID_PROFILEIMAGEURL",
        "INVALID_FILE_URL", "INVALID_REQUEST", "MISSING_REQUIRED_FIELD",
        "POST_FILE_LIMIT_EXCEEDED",
    })

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError):
        logger.warning(
            "Validation error: Path=%s, Errors=%s",
            request.url.path,
            exc.errors(),
        )
        code = ApiCode.INVALID_REQUEST_BODY.value
        for err in exc.errors():
            msg = err.get("msg", "")
            if isinstance(msg, str):
                for known in _KNOWN_VALIDATION_CODES:
                    if known in msg or msg == known:
                        code = known
                        break
                if code != ApiCode.INVALID_REQUEST_BODY.value:
                    break
        return JSONResponse(
            status_code=400,
            content={"code": code, "data": None},
        )

    @app.exception_handler(HTTPException)
    async def http_exception_handler(request: Request, exc: HTTPException):
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

        # 응답 포맷 통일: 우리 포맷(dict with code)이면 그대로, 아니면 code 매핑
        if isinstance(exc.detail, dict) and "code" in exc.detail:
            return JSONResponse(status_code=exc.status_code, content=exc.detail)
        code = HTTP_STATUS_TO_CODE.get(exc.status_code)
        if not code and isinstance(exc.detail, dict):
            code = exc.detail.get("code", ApiCode.HTTP_ERROR.value)
        if code is None:
            code = str(exc.detail) if exc.detail else ApiCode.HTTP_ERROR.value
        code_str = code.value if isinstance(code, ApiCode) else code
        return JSONResponse(
            status_code=exc.status_code,
            content={"code": code_str, "data": None},
        )

    # DB 예외: 중복키/무결성/연결실패 등 { code, data } 통일
    @app.exception_handler(pymysql.err.IntegrityError)
    async def integrity_error_handler(request: Request, exc: pymysql.err.IntegrityError):
        logger.warning(
            "DB IntegrityError: Path=%s, Errno=%s",
            request.url.path,
            getattr(exc, "args", ())[:1],
        )
        errno = getattr(exc, "args", (0, ""))[0] if exc.args else 0
        # 1062=Duplicate entry (UNIQUE 위반), 1452=FK violation
        if errno == 1062:
            return JSONResponse(status_code=409, content={"code": ApiCode.CONFLICT.value, "data": None})
        if errno in (1451, 1452):  # FK 제약 위반
            return JSONResponse(status_code=409, content={"code": ApiCode.CONSTRAINT_ERROR.value, "data": None})
        return JSONResponse(status_code=400, content={"code": ApiCode.INVALID_REQUEST.value, "data": None})

    @app.exception_handler(pymysql.err.OperationalError)
    async def operational_error_handler(request: Request, exc: pymysql.err.OperationalError):
        logger.error(
            "DB OperationalError: Path=%s, Errno=%s",
            request.url.path,
            getattr(exc, "args", ())[:1],
        )
        return JSONResponse(status_code=500, content={"code": ApiCode.DB_ERROR.value, "data": None})

    @app.exception_handler(pymysql.err.Error)
    async def pymysql_error_handler(request: Request, exc: pymysql.err.Error):
        logger.error(
            "DB Error: Path=%s, Exception=%s",
            request.url.path,
            type(exc).__name__,
        )
        return JSONResponse(status_code=500, content={"code": ApiCode.DB_ERROR.value, "data": None})

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
            content={"code": ApiCode.INTERNAL_SERVER_ERROR.value, "data": None},
        )

