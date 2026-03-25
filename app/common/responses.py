# ApiResponse 팩토리. Request.state.request_id 주입(X-Request-ID와 동일 값).
from typing import Any

from starlette.requests import Request

from app.common.codes import ApiCode
from app.common.schemas import ApiResponse


def get_request_id(request: Request) -> str:
    rid = getattr(request.state, "request_id", None)
    return rid if isinstance(rid, str) else ""


def api_response(
    request: Request,
    *,
    code: ApiCode | str = ApiCode.OK,
    data: Any = None,
    message: str | None = None,
) -> ApiResponse[Any]:
    return ApiResponse(
        code=code,
        data=data,
        message=message,
        request_id=get_request_id(request),
    )


def dump_api_response(
    request: Request,
    *,
    code: ApiCode | str = ApiCode.OK,
    data: Any = None,
    message: str | None = None,
) -> dict[str, Any]:
    return api_response(request, code=code, data=data, message=message).model_dump(
        mode="json", by_alias=True
    )
