# 댓글 요청/응답 DTO. CommentCreateRequest, CommentResponse, 목록 스키마.
from typing import List, Optional

from pydantic import Field, model_validator

from app.common import BaseSchema, UserStatus, UtcDatetime
from app.users.schema import RepresentativeDogInfo


class CommentIdData(BaseSchema):

    id: int


class CommentsPageData(BaseSchema):

    list: List["CommentResponse"] = Field(default_factory=list)
    total_count: int = 0
    total_pages: int = 0
    current_page: int = 1


class CommentUpsertRequest(BaseSchema):
    content: str = Field(..., min_length=1, max_length=500, description="댓글 내용 (1~500자)")


class CommentAuthorInfo(BaseSchema):
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


class CommentResponse(BaseSchema):
    id: int
    content: str
    author: CommentAuthorInfo
    created_at: UtcDatetime
    post_id: Optional[int] = None


CommentsPageData.model_rebuild()
