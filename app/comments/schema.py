# app/comments/schema.py
"""요청/응답 DTO."""

from typing import Optional

from pydantic import BaseModel, Field


class CommentCreateRequest(BaseModel):
    content: str = Field(..., min_length=1)


class CommentUpdateRequest(BaseModel):
    content: str = Field(..., min_length=1)


class CommentAuthorInfo(BaseModel):
    userId: int
    nickname: str
    profileImageUrl: str


class CommentResponse(BaseModel):
    commentId: int
    content: str
    author: CommentAuthorInfo
    createdAt: str
    postId: Optional[int] = None
