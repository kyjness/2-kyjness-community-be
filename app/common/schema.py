# 전역 스키마 기반. 모든 API 요청/응답은 BaseSchema 상속 → Snake/Camel 자동 변환 및 ORM 매핑.
from typing import Generic, List, Optional, TypeVar

from pydantic import BaseModel, ConfigDict, Field


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
    code: str
    data: Optional[T] = None
    message: Optional[str] = None


class PaginatedResponse(BaseSchema, Generic[T]):
    list: List[T] = Field(default_factory=list)
    has_more: bool = False
    total: int = 0


class RootData(BaseSchema):
    message: str = ""
    version: str = ""
    docs: str = ""
