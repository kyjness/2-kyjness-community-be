# 댓글 요청/응답 DTO. CommentCreateRequest, CommentResponse, 목록 스키마.

from pydantic import Field, model_validator

from app.common import BaseSchema, UserStatus, UtcDatetime
from app.users.schema import RepresentativeDogInfo


class CommentIdData(BaseSchema):
    id: int


class CommentsPageData(BaseSchema):
    items: list["CommentResponse"] = Field(default_factory=list)
    total_count: int = 0
    total_pages: int = 0
    current_page: int = 1


class CommentUpsertRequest(BaseSchema):
    content: str = Field(..., min_length=1, max_length=500, description="댓글 내용 (1~500자)")
    parent_id: int | None = None


class CommentAuthorInfo(BaseSchema):
    id: int
    nickname: str
    profile_image_id: int | None = None
    profile_image_url: str | None = None
    representative_dog: RepresentativeDogInfo | None = None

    @model_validator(mode="wrap")
    @classmethod
    def anonymize_inactive(cls, data, handler):
        status = getattr(data, "status", None)
        if status is not None and not UserStatus.is_active_value(status):
            if hasattr(data, "id"):
                return handler(
                    {
                        "id": data.id,
                        "nickname": "알수없음",
                        "profile_image_id": None,
                        "profile_image_url": None,
                        "representative_dog": None,
                    }
                )
        return handler(data)


class CommentResponse(BaseSchema):
    id: int
    content: str
    author: CommentAuthorInfo
    created_at: UtcDatetime
    updated_at: UtcDatetime
    post_id: int | None = None
    parent_id: int | None = None
    like_count: int = 0
    is_liked: bool = False
    is_edited: bool = False
    is_deleted: bool = False
    replies: list["CommentResponse"] = Field(default_factory=list)


CommentResponse.model_rebuild()
CommentsPageData.model_rebuild()
