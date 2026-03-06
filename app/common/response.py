# 공통 API 에러 응답: raise_http_error (HTTPException + code/data/message).
from typing import Optional, Union

from fastapi import HTTPException

from app.common.codes import ApiCode


def raise_http_error(
    status_code: int,
    error_code: Union[str, ApiCode],
    message: Optional[str] = None,
) -> None:
    code_str = error_code.value if isinstance(error_code, ApiCode) else error_code
    detail: dict = {"code": code_str, "data": None}
    if message is not None:
        detail["message"] = message
    raise HTTPException(status_code=status_code, detail=detail)
