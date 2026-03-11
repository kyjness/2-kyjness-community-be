# 전역 예외 핸들러. 모든 에러 응답을 { code, message, data: null } 형태로 통일.
# core는 도메인 Model을 import하지 않음. 500 시 클라이언트에는 스택/쿼리 노출 금지, 서버 로그에만 request_id와 함께 기록.
import logging
from collections.abc import Sequence
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.exc import DatabaseError, IntegrityError, OperationalError

from app.common import ApiCode
from app.common.exceptions import BaseProjectException

logger = logging.getLogger(__name__)

# 500 에러 시 클라이언트에 반환할 마스킹 메시지 (스택/DB 내부 정보 절대 노출 금지)
MASKED_500_MESSAGE = "Internal Server Error"


def _error_body(code: str, message: str = "", data: object | None = None) -> dict:
    """프론트 파싱용 표준 에러 응답 body. message는 항상 문자열로 제공."""
    return {"code": code, "message": message if message else "", "data": data}


HTTP_STATUS_TO_CODE = {
    400: ApiCode.INVALID_REQUEST,
    401: ApiCode.UNAUTHORIZED,
    403: ApiCode.FORBIDDEN,
    404: ApiCode.NOT_FOUND,
    405: ApiCode.METHOD_NOT_ALLOWED,
    409: ApiCode.CONFLICT,
    413: ApiCode.PAYLOAD_TOO_LARGE,
    422: ApiCode.UNPROCESSABLE_ENTITY,
    429: ApiCode.RATE_LIMIT_EXCEEDED,
    500: ApiCode.INTERNAL_SERVER_ERROR,
}


def register_exception_handlers(app: FastAPI) -> None:
    _VALIDATION_CODE_NAMES = frozenset(
        {
            ApiCode.INVALID_REQUEST_BODY.name,
            ApiCode.INVALID_REQUEST.name,
            ApiCode.INVALID_FILE_FORMAT.name,
            ApiCode.MISSING_REQUIRED_FIELD.name,
            ApiCode.POST_FILE_LIMIT_EXCEEDED.name,
        }
    )

    def _pick_validation_code(request: Request, errors: Sequence[Any]) -> str:
        for err in errors:
            msg = err.get("msg", "") if isinstance(err.get("msg"), str) else ""
            for name in _VALIDATION_CODE_NAMES:
                if name in msg or msg == name:
                    return getattr(ApiCode, name).value
        return ApiCode.INVALID_REQUEST_BODY.value

    def _first_validation_message(errors: Sequence[Any]) -> str | None:
        if not errors:
            return None
        first = errors[0]
        if isinstance(first, dict):
            msg = first.get("msg")
            if isinstance(msg, str) and msg:
                return msg
        return None

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError):
        errors = exc.errors()
        code = _pick_validation_code(request, errors)
        message = _first_validation_message(errors) or ""
        return JSONResponse(
            status_code=400,
            content=_error_body(code, message, data=None),
        )

    @app.exception_handler(HTTPException)
    async def http_exception_handler(request: Request, exc: HTTPException):
        """422 등 FastAPI 기본 HTTP 에러를 표준 { code, message, data } 형식으로 통일."""
        headers = dict(exc.headers) if exc.headers else {}
        if isinstance(exc.detail, dict) and "code" in exc.detail:
            detail = exc.detail
            code_str = detail.get("code", "")
            message = detail.get("message", "") if isinstance(detail.get("message"), str) else ""
            content = _error_body(code_str, message, detail.get("data"))
        else:
            code = HTTP_STATUS_TO_CODE.get(exc.status_code) or ApiCode.HTTP_ERROR
            code_str = code.value if isinstance(code, ApiCode) else code
            message = ""
            if isinstance(exc.detail, str):
                message = exc.detail
            elif isinstance(exc.detail, dict) and "message" in exc.detail:
                message = exc.detail.get("message") or ""
            content = _error_body(code_str, message, None)
        return JSONResponse(status_code=exc.status_code, content=content, headers=headers)

    @app.exception_handler(IntegrityError)
    async def integrity_error_handler(request: Request, exc: IntegrityError):
        request_id = getattr(request.state, "request_id", "")
        logger.error(
            "request_id=%s DB IntegrityError: path=%s exception=%s: %s",
            request_id,
            request.url.path,
            type(exc).__name__,
            str(exc),
        )
        orig = getattr(exc, "orig", None)
        errno = (orig.args[0] if orig and getattr(orig, "args", None) else 0) or 0
        pgcode = getattr(orig, "pgcode", None) if orig else None
        err_msg = (orig.args[1] if orig and len(getattr(orig, "args", ())) > 1 else str(exc)) or ""
        is_duplicate_key = errno == 1062 or pgcode == "23505"
        if is_duplicate_key:
            msg_lower = err_msg.lower() if isinstance(err_msg, str) else ""
            if "email" in msg_lower or "key 'email'" in msg_lower:
                return JSONResponse(
                    status_code=409,
                    content=_error_body(ApiCode.EMAIL_ALREADY_EXISTS.value, "", None),
                )
            if "nickname" in msg_lower or "key 'nickname'" in msg_lower:
                return JSONResponse(
                    status_code=409,
                    content=_error_body(ApiCode.NICKNAME_ALREADY_EXISTS.value, "", None),
                )
            return JSONResponse(
                status_code=409,
                content=_error_body(ApiCode.CONFLICT.value, "", None),
            )
        if errno in (1451, 1452):
            return JSONResponse(
                status_code=409,
                content=_error_body(ApiCode.CONSTRAINT_ERROR.value, "", None),
            )
        return JSONResponse(
            status_code=400,
            content=_error_body(ApiCode.INVALID_REQUEST.value, "", None),
        )

    @app.exception_handler(OperationalError)
    async def operational_error_handler(request: Request, exc: OperationalError):
        request_id = getattr(request.state, "request_id", "")
        logger.exception(
            "request_id=%s DB OperationalError: path=%s exception=%s: %s",
            request_id,
            request.url.path,
            type(exc).__name__,
            str(exc),
        )
        return JSONResponse(
            status_code=500,
            content=_error_body(ApiCode.DB_ERROR.value, MASKED_500_MESSAGE, None),
        )

    @app.exception_handler(DatabaseError)
    async def database_error_handler(request: Request, exc: DatabaseError):
        request_id = getattr(request.state, "request_id", "")
        logger.exception(
            "request_id=%s DB DatabaseError: path=%s exception=%s: %s",
            request_id,
            request.url.path,
            type(exc).__name__,
            str(exc),
        )
        return JSONResponse(
            status_code=500,
            content=_error_body(ApiCode.DB_ERROR.value, MASKED_500_MESSAGE, None),
        )

    @app.exception_handler(BaseProjectException)
    async def project_exception_handler(request: Request, exc: BaseProjectException):
        code_val = exc.code.value if isinstance(exc.code, ApiCode) else str(exc.code)
        message = getattr(exc, "message", None)
        message_str = message if isinstance(message, str) else ""
        content = _error_body(code_val, message_str, getattr(exc, "data", None))
        return JSONResponse(status_code=exc.status_code, content=content)

    @app.exception_handler(Exception)
    async def general_exception_handler(request: Request, exc: Exception):
        """Catch-all 500: 클라이언트에는 스택/쿼리 노출 금지, 서버 로그에만 request_id와 함께 기록."""
        request_id = getattr(request.state, "request_id", "") or ""
        logger.exception(
            "request_id=%s path=%s status=500 unhandled exception: %s",
            request_id,
            request.url.path,
            type(exc).__name__,
        )
        return JSONResponse(
            status_code=500,
            content=_error_body(ApiCode.INTERNAL_SERVER_ERROR.value, MASKED_500_MESSAGE, None),
        )
