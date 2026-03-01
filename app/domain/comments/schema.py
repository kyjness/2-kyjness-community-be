# 댓글 요청/응답 DTO. CommentCreateRequest, CommentResponse, 목록 스키마.
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class CommentUpsertRequest(BaseModel):
    content: str = Field(..., min_length=1, max_length=500, description="댓글 내용 (1~500자)")


class CommentAuthorInfo(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int = Field(serialization_alias="userId")
    nickname: str
    profile_image_id: Optional[int] = Field(default=None, serialization_alias="profileImageId")
    profile_image_url: Optional[str] = Field(default=None, serialization_alias="profileImageUrl")


class CommentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int = Field(serialization_alias="commentId")
    content: str
    author: CommentAuthorInfo
    created_at: datetime = Field(serialization_alias="createdAt")
    post_id: Optional[int] = Field(default=None, serialization_alias="postId")
