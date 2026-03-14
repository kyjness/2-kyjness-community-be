# 공통 스키마·응답 래퍼. BaseSchema, ApiResponse, PaginatedResponse 등.
from typing import Generic, TypeVar

from pydantic import BaseModel, ConfigDict, Field

from app.common.codes import ApiCode


def to_camel(name: str) -> str:
    parts = name.split("_")
    return parts[0].lower() + "".join(w.capitalize() for w in parts[1:])


class BaseSchema(BaseModel):
    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
        from_attributes=True,
    )


T = TypeVar("T")


class ApiResponse(BaseSchema, Generic[T]):
    """code는 ApiCode enum 또는 str. 직렬화 시 enum은 자동으로 .value로 나감."""
    code: ApiCode | str
    data: T | None = None
    message: str | None = None

    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
        from_attributes=True,
        use_enum_values=True,
    )


class PaginatedResponse(BaseSchema, Generic[T]):
    items: list[T] = Field(default_factory=list)
    has_more: bool = False
    total: int = 0


class RootData(BaseSchema):
    message: str = ""
    version: str = ""
    docs: str = ""
