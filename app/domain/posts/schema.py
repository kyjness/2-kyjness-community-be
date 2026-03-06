# 게시글 요청/응답 DTO. PostCreateRequest, PostResponse, 피드·상세 스키마.
from typing import List, Optional

from pydantic import Field, field_validator, model_validator

from app.common import BaseSchema, UserStatus, UtcDatetime
from app.users.schema import RepresentativeDogInfo


class PostIdData(BaseSchema):

    id: int


class LikeCountData(BaseSchema):

    like_count: int


class PostCreateRequest(BaseSchema):
    title: str = Field(..., min_length=1, max_length=26)
    content: str = Field(..., min_length=1, max_length=50_000)
    image_ids: Optional[List[int]] = Field(default=None, max_length=5)

    @field_validator("image_ids")
    @classmethod
    def image_ids_max_five_create(cls, v: Optional[List[int]]) -> Optional[List[int]]:
        if v is not None and len(v) > 5:
            raise ValueError("POST_FILE_LIMIT_EXCEEDED")
        return v


class PostUpdateRequest(BaseSchema):
    title: Optional[str] = Field(default=None, min_length=1, max_length=26)
    content: Optional[str] = Field(default=None, min_length=1, max_length=50_000)
    image_ids: Optional[List[int]] = Field(default=None)

    @field_validator("image_ids")
    @classmethod
    def image_ids_max_five_update(cls, v: Optional[List[int]]) -> Optional[List[int]]:
        if v is not None and len(v) > 5:
            raise ValueError("POST_FILE_LIMIT_EXCEEDED")
        return v


class AuthorInfo(BaseSchema):
    id: int
    nickname: str
    profile_image_id: Optional[int] = None
    profile_image_url: Optional[str] = None
    representative_dog: Optional[RepresentativeDogInfo] = None

    @model_validator(mode="wrap")
    @classmethod
    def anonymize_inactive(cls, data, handler):
        status = getattr(data, "status", None)
        if status is not None and not UserStatus.is_active_value(status):
            if hasattr(data, "id"):
                return handler({
                    "id": data.id,
                    "nickname": "알수없음",
                    "profile_image_id": None,
                    "profile_image_url": None,
                    "representative_dog": None,
                })
        return handler(data)


class FileInfo(BaseSchema):
    id: int
    file_url: Optional[str] = None
    image_id: Optional[int] = None


class PostResponse(BaseSchema):
    id: int
    title: str
    content: str
    view_count: int = 0
    like_count: int = 0
    comment_count: int = 0
    author: AuthorInfo
    files: List[FileInfo] = Field(default_factory=list)
    created_at: UtcDatetime
