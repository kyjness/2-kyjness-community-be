import logging

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError, OperationalError

from app.common import ApiCode

logger = logging.getLogger(__name__)

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
    _KNOWN_CODES = frozenset({
        "INVALID_EMAIL_FORMAT", "INVALID_PASSWORD_FORMAT", "INVALID_NICKNAME_FORMAT",
        "INVALID_PROFILEIMAGEURL", "INVALID_FILE_URL", "INVALID_REQUEST",
        "MISSING_REQUIRED_FIELD", "POST_FILE_LIMIT_EXCEEDED",
    })

    def _pick_validation_code(request: Request, errors: list) -> str:
        is_login = "/auth/login" in request.url.path or request.url.path.endswith("/login")
        found_codes = []
        for err in errors:
            loc = err.get("loc", ())
            msg = err.get("msg", "") if isinstance(err.get("msg"), str) else ""
            if "email" in loc or ("email" in msg.lower() and "valid" in msg.lower()):
                found_codes.append("INVALID_EMAIL_FORMAT")
            for known in _KNOWN_CODES:
                if known in msg or msg == known:
                    found_codes.append(known)
                    break
        if is_login:
            for code in found_codes:
                if code == "INVALID_EMAIL_FORMAT":
                    return code
        for code in found_codes:
            return code
        return ApiCode.INVALID_REQUEST_BODY.value

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError):
        code = _pick_validation_code(request, exc.errors())
        return JSONResponse(status_code=400, content={"code": code, "data": None})

    @app.exception_handler(HTTPException)
    async def http_exception_handler(request: Request, exc: HTTPException):
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

    @app.exception_handler(IntegrityError)
    async def integrity_error_handler(request: Request, exc: IntegrityError):
        orig = getattr(exc, "orig", None)
        errno = (orig.args[0] if orig and getattr(orig, "args", None) else 0) or 0
        err_msg = (orig.args[1] if orig and len(getattr(orig, "args", ())) > 1 else str(exc)) or ""
        if errno == 1062:
            msg_lower = err_msg.lower() if isinstance(err_msg, str) else ""
            if "email" in msg_lower or "key 'email'" in msg_lower:
                return JSONResponse(status_code=409, content={"code": ApiCode.EMAIL_ALREADY_EXISTS.value, "data": None})
            if "nickname" in msg_lower or "key 'nickname'" in msg_lower:
                return JSONResponse(status_code=409, content={"code": ApiCode.NICKNAME_ALREADY_EXISTS.value, "data": None})
            return JSONResponse(status_code=409, content={"code": ApiCode.CONFLICT.value, "data": None})
        if errno in (1451, 1452):
            return JSONResponse(status_code=409, content={"code": ApiCode.CONSTRAINT_ERROR.value, "data": None})
        return JSONResponse(status_code=400, content={"code": ApiCode.INVALID_REQUEST.value, "data": None})

    @app.exception_handler(OperationalError)
    async def operational_error_handler(request: Request, exc: OperationalError):
        logger.error(
            "DB OperationalError: Path=%s, Exception=%s",
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

