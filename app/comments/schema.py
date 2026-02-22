# app/comments/schema.py

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field, field_validator


class CommentUpsertRequest(BaseModel):
    content: str = Field(..., min_length=1, max_length=500, description="댓글 내용 (1~500자)")


class CommentAuthorInfo(BaseModel):
    id: int = Field(serialization_alias="userId")
    nickname: str
    profile_image_url: str = Field(serialization_alias="profileImageUrl", default="")

    @field_validator("profile_image_url", mode="before")
    @classmethod
    def empty_str_if_none(cls, v):
        return (v or "").strip() or ""


class CommentResponse(BaseModel):
    id: int = Field(serialization_alias="commentId")
    content: str
    author: CommentAuthorInfo
    created_at: datetime = Field(serialization_alias="createdAt")
    post_id: Optional[int] = Field(default=None, serialization_alias="postId")

    @classmethod
    def from_rows(cls, comment_row: dict, author_row: dict, post_id: Optional[int] = None) -> "CommentResponse":
        """comment_row + author_row → 응답. 내부에서 model_validate 활용."""
        data = {
            **comment_row,
            "author": author_row,
            "post_id": post_id or comment_row.get("post_id"),
        }
        return cls.model_validate(data)
