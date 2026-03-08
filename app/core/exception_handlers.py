# 전역 예외 핸들러. RequestValidationError, HTTPException, DB 예외, 도메인 예외 → { code, data, message? } 통일.
# core는 특정 Model을 import하지 않음. 도메인 예외는 Service에서 던지고, 예외 객체만으로 응답 구성.
import logging
from typing import Optional

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.exc import DatabaseError, IntegrityError, OperationalError

from app.common import ApiCode
from app.common.exceptions import BaseProjectException

logger = logging.getLogger(__name__)

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

    def _pick_validation_code(request: Request, errors: list) -> str:
        for err in errors:
            msg = err.get("msg", "") if isinstance(err.get("msg"), str) else ""
            for name in _VALIDATION_CODE_NAMES:
                if name in msg or msg == name:
                    return getattr(ApiCode, name).value
        return ApiCode.INVALID_REQUEST_BODY.value

    def _first_validation_message(errors: list) -> Optional[str]:
        if not errors:
            return None
        first = errors[0]
        if isinstance(first, dict):
            msg = first.get("msg")
            if isinstance(msg, str) and msg:
                return msg
        return None

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(
        request: Request, exc: RequestValidationError
    ):
        errors = exc.errors()
        code = _pick_validation_code(request, errors)
        content: dict = {"code": code, "data": None}
        message = _first_validation_message(errors)
        if message:
            content["message"] = message
        return JSONResponse(status_code=400, content=content)

    @app.exception_handler(HTTPException)
    async def http_exception_handler(request: Request, exc: HTTPException):
        """detail이 dict가 아니면 code·message로 변환해 클라이언트 응답 형식 통일."""
        headers = dict(exc.headers) if exc.headers else {}
        if isinstance(exc.detail, dict) and "code" in exc.detail:
            return JSONResponse(
                status_code=exc.status_code, content=exc.detail, headers=headers
            )
        code = HTTP_STATUS_TO_CODE.get(exc.status_code) or ApiCode.HTTP_ERROR
        code_str = code.value if isinstance(code, ApiCode) else code
        message = None
        if isinstance(exc.detail, str):
            message = exc.detail
        elif isinstance(exc.detail, dict) and "message" in exc.detail:
            message = exc.detail.get("message")
        content = {"code": code_str, "data": None}
        if message is not None:
            content["message"] = message
        return JSONResponse(
            status_code=exc.status_code, content=content, headers=headers
        )

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
        pgcode = (
            getattr(orig, "pgcode", None) if orig else None
        )  # PostgreSQL: 23505 = UniqueViolation
        err_msg = (
            orig.args[1] if orig and len(getattr(orig, "args", ())) > 1 else str(exc)
        ) or ""
        is_duplicate_key = errno == 1062 or pgcode == "23505"
        if is_duplicate_key:
            msg_lower = err_msg.lower() if isinstance(err_msg, str) else ""
            if "email" in msg_lower or "key 'email'" in msg_lower:
                return JSONResponse(
                    status_code=409,
                    content={"code": ApiCode.EMAIL_ALREADY_EXISTS.value, "data": None},
                )
            if "nickname" in msg_lower or "key 'nickname'" in msg_lower:
                return JSONResponse(
                    status_code=409,
                    content={
                        "code": ApiCode.NICKNAME_ALREADY_EXISTS.value,
                        "data": None,
                    },
                )
            # 좋아요 중복 등: Service에서 IntegrityError를 catch하여 AlreadyLikedException(data=...)으로 변환.
            # 여기서는 Model을 참조하지 않고 409 CONFLICT만 반환.
            return JSONResponse(
                status_code=409, content={"code": ApiCode.CONFLICT.value, "data": None}
            )
        if errno in (1451, 1452):
            return JSONResponse(
                status_code=409,
                content={"code": ApiCode.CONSTRAINT_ERROR.value, "data": None},
            )
        return JSONResponse(
            status_code=400,
            content={"code": ApiCode.INVALID_REQUEST.value, "data": None},
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
            status_code=500, content={"code": ApiCode.DB_ERROR.value, "data": None}
        )

    @app.exception_handler(DatabaseError)
    async def database_error_handler(request: Request, exc: DatabaseError):
        """IntegrityError/OperationalError 외 DB 예외(InterfaceError, DataError, ProgrammingError 등) → DB_ERROR."""
        request_id = getattr(request.state, "request_id", "")
        logger.exception(
            "request_id=%s DB DatabaseError: path=%s exception=%s: %s",
            request_id,
            request.url.path,
            type(exc).__name__,
            str(exc),
        )
        return JSONResponse(
            status_code=500, content={"code": ApiCode.DB_ERROR.value, "data": None}
        )

    @app.exception_handler(BaseProjectException)
    async def project_exception_handler(request: Request, exc: BaseProjectException):
        """도메인 커스텀 예외 → ApiResponse 규격 { code, data, message? }. 예외 객체만 사용, Model 미참조."""
        code_val = exc.code.value if isinstance(exc.code, ApiCode) else str(exc.code)
        content: dict = {"code": code_val, "data": getattr(exc, "data", None)}
        if getattr(exc, "message", None) is not None:
            content["message"] = exc.message
        return JSONResponse(status_code=exc.status_code, content=content)

    @app.exception_handler(Exception)
    async def general_exception_handler(request: Request, exc: Exception):
        request_id = getattr(request.state, "request_id", "")
        logger.exception(
            "request_id=%s path=%s status=500 unhandled exception: %s",
            request_id,
            request.url.path,
            exc,
        )
        return JSONResponse(
            status_code=500,
            content={"code": ApiCode.INTERNAL_SERVER_ERROR.value, "data": None},
        )
