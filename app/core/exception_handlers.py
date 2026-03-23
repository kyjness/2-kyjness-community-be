# 전역 예외 핸들러. 모든 에러 응답을 ApiResponse와 동일한 바디(code, message, data, requestId)로 통일.
# 500 시 클라이언트에는 스택/쿼리 노출 금지. 서버 로그는 에러 시에만 구조화(JSON 한 줄) + 필요 시 traceback.
import json
import logging
from collections.abc import Sequence
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.exc import DatabaseError, IntegrityError, OperationalError

from app.common import ApiCode
from app.common.exceptions import BaseProjectException
from app.common.responses import get_request_id

logger = logging.getLogger(__name__)

MASKED_500_MESSAGE = "Internal Server Error"


def _error_payload(
    code: str,
    message: str = "",
    data: object | None = None,
    *,
    request: Request,
) -> dict[str, Any]:
    return {
        "code": code,
        "message": message if message else "",
        "data": data,
        "requestId": get_request_id(request),
    }


def _log_error_structured(
    request: Request,
    event: str,
    exc: BaseException | None = None,
    **fields: Any,
) -> None:
    payload: dict[str, Any] = {
        "event": event,
        "request_id": get_request_id(request),
        "path": request.url.path,
        "method": request.method,
        **fields,
    }
    if exc is not None:
        payload["exc_type"] = type(exc).__name__
        payload["exc_msg"] = str(exc)[:2000]
    line = json.dumps(payload, ensure_ascii=False)
    if exc is not None:
        logger.exception("%s", line)
    else:
        logger.error("%s", line)


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
            content=_error_payload(code, message, None, request=request),
        )

    @app.exception_handler(HTTPException)
    async def http_exception_handler(request: Request, exc: HTTPException):
        headers = dict(exc.headers) if exc.headers else {}
        if isinstance(exc.detail, dict) and "code" in exc.detail:
            detail = exc.detail
            code_str = detail.get("code", "")
            message = detail.get("message", "") if isinstance(detail.get("message"), str) else ""
            content = _error_payload(code_str, message, detail.get("data"), request=request)
        else:
            code = HTTP_STATUS_TO_CODE.get(exc.status_code) or ApiCode.HTTP_ERROR
            code_str = code.value if isinstance(code, ApiCode) else code
            message = ""
            if isinstance(exc.detail, str):
                message = exc.detail
            elif isinstance(exc.detail, dict) and "message" in exc.detail:
                message = exc.detail.get("message") or ""
            content = _error_payload(code_str, message, None, request=request)
        return JSONResponse(status_code=exc.status_code, content=content, headers=headers)

    @app.exception_handler(IntegrityError)
    async def integrity_error_handler(request: Request, exc: IntegrityError):
        orig = getattr(exc, "orig", None)
        errno = (orig.args[0] if orig and getattr(orig, "args", None) else 0) or 0
        pgcode = getattr(orig, "pgcode", None) if orig else None
        err_msg = (orig.args[1] if orig and len(getattr(orig, "args", ())) > 1 else str(exc)) or ""
        is_duplicate_key = errno == 1062 or pgcode == "23505"
        if is_duplicate_key:
            logger.warning(
                "%s",
                json.dumps(
                    {
                        "event": "db_integrity_duplicate",
                        "request_id": get_request_id(request),
                        "path": request.url.path,
                        "pgcode": pgcode,
                    },
                    ensure_ascii=False,
                ),
            )
            msg_lower = err_msg.lower() if isinstance(err_msg, str) else ""
            if "email" in msg_lower or "key 'email'" in msg_lower:
                return JSONResponse(
                    status_code=409,
                    content=_error_payload(ApiCode.EMAIL_ALREADY_EXISTS.value, "", None, request=request),
                )
            if "nickname" in msg_lower or "key 'nickname'" in msg_lower:
                return JSONResponse(
                    status_code=409,
                    content=_error_payload(
                        ApiCode.NICKNAME_ALREADY_EXISTS.value, "", None, request=request
                    ),
                )
            return JSONResponse(
                status_code=409,
                content=_error_payload(ApiCode.CONFLICT.value, "", None, request=request),
            )
        if errno in (1451, 1452):
            _log_error_structured(request, "db_integrity_fk", exc, errno=errno)
            return JSONResponse(
                status_code=409,
                content=_error_payload(ApiCode.CONSTRAINT_ERROR.value, "", None, request=request),
            )
        _log_error_structured(request, "db_integrity_other", exc, errno=errno, pgcode=pgcode)
        return JSONResponse(
            status_code=400,
            content=_error_payload(ApiCode.INVALID_REQUEST.value, "", None, request=request),
        )

    @app.exception_handler(OperationalError)
    async def operational_error_handler(request: Request, exc: OperationalError):
        _log_error_structured(request, "db_operational_error", exc)
        return JSONResponse(
            status_code=500,
            content=_error_payload(ApiCode.DB_ERROR.value, MASKED_500_MESSAGE, None, request=request),
        )

    @app.exception_handler(DatabaseError)
    async def database_error_handler(request: Request, exc: DatabaseError):
        _log_error_structured(request, "db_database_error", exc)
        return JSONResponse(
            status_code=500,
            content=_error_payload(ApiCode.DB_ERROR.value, MASKED_500_MESSAGE, None, request=request),
        )

    @app.exception_handler(BaseProjectException)
    async def project_exception_handler(request: Request, exc: BaseProjectException):
        code_val = exc.code.value if isinstance(exc.code, ApiCode) else str(exc.code)
        message = getattr(exc, "message", None)
        message_str = message if isinstance(message, str) else ""
        content = _error_payload(code_val, message_str, getattr(exc, "data", None), request=request)
        return JSONResponse(status_code=exc.status_code, content=content)

    @app.exception_handler(Exception)
    async def general_exception_handler(request: Request, exc: Exception):
        _log_error_structured(request, "unhandled_exception", exc)
        return JSONResponse(
            status_code=500,
            content=_error_payload(
                ApiCode.INTERNAL_SERVER_ERROR.value, MASKED_500_MESSAGE, None, request=request
            ),
        )
