# app/posts/schema.py
"""요청/응답 DTO."""

from typing import List, Optional

from pydantic import BaseModel, Field, field_validator


class PostCreateRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=26)
    content: str = Field(..., min_length=1)
    imageIds: Optional[List[int]] = Field(default=None, max_length=5)

    @field_validator("imageIds")
    @classmethod
    def image_ids_max_five_create(cls, v: Optional[List[int]]) -> Optional[List[int]]:
        if v is not None and len(v) > 5:
            raise ValueError("POST_FILE_LIMIT_EXCEEDED")
        return v


class PostUpdateRequest(BaseModel):
    title: Optional[str] = Field(default=None, min_length=1, max_length=26)
    content: Optional[str] = Field(default=None, min_length=1)
    imageIds: Optional[List[int]] = Field(default=None)

    @field_validator("imageIds")
    @classmethod
    def image_ids_max_five_update(cls, v: Optional[List[int]]) -> Optional[List[int]]:
        if v is not None and len(v) > 5:
            raise ValueError("POST_FILE_LIMIT_EXCEEDED")
        return v


class AuthorInfo(BaseModel):
    userId: int
    nickname: str
    profileImageUrl: str


class FileInfo(BaseModel):
    fileId: int
    fileUrl: str
    imageId: Optional[int] = None


class PostResponse(BaseModel):
    postId: int
    title: str
    content: str
    hits: int
    likeCount: int
    commentCount: int
    author: AuthorInfo
    files: List[FileInfo] = Field(default_factory=list)
    createdAt: str
