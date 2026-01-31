# app/core/response.py
"""공통 응답 포맷: 모든 성공/실패는 { "code": "SOME_CODE", "data": ... } 통일. 실패 시 data는 null."""

from fastapi import HTTPException


def success_response(code: str, data=None):
    """성공 응답 dict. Route에서 그대로 반환."""
    return {"code": code, "data": data}


def raise_http_error(status_code: int, error_code: str) -> None:
    """HTTPException 발생 (detail 포맷 통일). 전역 exception_handler가 그대로 반환."""
    raise HTTPException(status_code=status_code, detail={"code": error_code, "data": None})
