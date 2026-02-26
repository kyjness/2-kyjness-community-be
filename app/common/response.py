from typing import Any, Optional, Union

from fastapi import HTTPException
from pydantic import BaseModel, ConfigDict

from app.common.codes import ApiCode


def _serialize_data(data: Any) -> Any:
    if isinstance(data, BaseModel):
        return data.model_dump(by_alias=True)
    if isinstance(data, list):
        return [_serialize_data(x) for x in data]
    if isinstance(data, dict):
        return {k: _serialize_data(v) for k, v in data.items()}
    return data


def success_response(code: Union[str, ApiCode], data=None) -> dict:
    code_str = code.value if isinstance(code, ApiCode) else code
    return {"code": code_str, "data": _serialize_data(data) if data is not None else data}


def raise_http_error(status_code: int, error_code: Union[str, ApiCode], message: Optional[str] = None) -> None:
    code_str = error_code.value if isinstance(error_code, ApiCode) else error_code
    detail: dict = {"code": code_str, "data": None}
    if message is not None:
        detail["message"] = message
    raise HTTPException(status_code=status_code, detail=detail)


class ApiResponse(BaseModel):
    model_config = ConfigDict(extra="allow")

    code: str
    data: Optional[Any] = None
