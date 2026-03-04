# 전역 예외 핸들러. RequestValidationError, HTTPException, DB 예외 → { code, data } 통일.
import logging

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError, OperationalError

from app.common import ApiCode
from app.db import get_connection
from app.posts.model import PostsModel

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
        "INVALID_REQUEST_BODY", "INVALID_REQUEST", "INVALID_FILE_FORMAT",
        "MISSING_REQUIRED_FIELD", "POST_FILE_LIMIT_EXCEEDED",
    })

    def _pick_validation_code(request: Request, errors: list) -> str:
        for err in errors:
            msg = err.get("msg", "") if isinstance(err.get("msg"), str) else ""
            for known in _KNOWN_CODES:
                if known in msg or msg == known:
                    return known
        return ApiCode.INVALID_REQUEST_BODY.value

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError):
        code = _pick_validation_code(request, exc.errors())
        return JSONResponse(status_code=400, content={"code": code, "data": None})

    @app.exception_handler(HTTPException)
    async def http_exception_handler(request: Request, exc: HTTPException):
        """detail이 dict가 아니면 code·message로 변환해 클라이언트 응답 형식 통일."""
        headers = dict(exc.headers) if exc.headers else {}
        if isinstance(exc.detail, dict) and "code" in exc.detail:
            return JSONResponse(status_code=exc.status_code, content=exc.detail, headers=headers)
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
        err_msg = (orig.args[1] if orig and len(getattr(orig, "args", ())) > 1 else str(exc)) or ""
        if errno == 1062:
            msg_lower = err_msg.lower() if isinstance(err_msg, str) else ""
            if "email" in msg_lower or "key 'email'" in msg_lower:
                return JSONResponse(status_code=409, content={"code": ApiCode.EMAIL_ALREADY_EXISTS.value, "data": None})
            if "nickname" in msg_lower or "key 'nickname'" in msg_lower:
                return JSONResponse(status_code=409, content={"code": ApiCode.NICKNAME_ALREADY_EXISTS.value, "data": None})
            parts = request.url.path.rstrip("/").split("/")
            if "posts" in parts and "likes" in parts:
                try:
                    idx = parts.index("posts")
                    if idx + 1 < len(parts) and parts[idx + 1].isdigit():
                        post_id = int(parts[idx + 1])
                        with get_connection() as db:
                            like_count = PostsModel.get_like_count(post_id, db=db)
                        return JSONResponse(status_code=200, content={"code": ApiCode.ALREADY_LIKED.value, "data": {"likeCount": like_count}})
                except (ValueError, IndexError):
                    pass
            return JSONResponse(status_code=409, content={"code": ApiCode.CONFLICT.value, "data": None})
        if errno in (1451, 1452):
            return JSONResponse(status_code=409, content={"code": ApiCode.CONSTRAINT_ERROR.value, "data": None})
        return JSONResponse(status_code=400, content={"code": ApiCode.INVALID_REQUEST.value, "data": None})

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
        return JSONResponse(status_code=500, content={"code": ApiCode.DB_ERROR.value, "data": None})

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

