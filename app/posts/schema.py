# app/posts/schema.py

from datetime import datetime
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
    id: int = Field(serialization_alias="userId")
    nickname: str
    profile_image_url: str = Field(serialization_alias="profileImageUrl", default="")

    @field_validator("profile_image_url", mode="before")
    @classmethod
    def empty_str_if_none(cls, v):
        return (v or "").strip() or ""


class FileInfo(BaseModel):
    id: int = Field(serialization_alias="fileId")
    file_url: str = Field(serialization_alias="fileUrl", default="")
    image_id: Optional[int] = Field(default=None, serialization_alias="imageId")

    @field_validator("file_url", mode="before")
    @classmethod
    def empty_str_if_none(cls, v):
        return (v or "").strip() or ""


class PostResponse(BaseModel):
    id: int = Field(serialization_alias="postId")
    title: str
    content: str
    view_count: int = Field(serialization_alias="hits", default=0)
    like_count: int = Field(serialization_alias="likeCount", default=0)
    comment_count: int = Field(serialization_alias="commentCount", default=0)
    author: AuthorInfo
    files: List[FileInfo] = Field(default_factory=list)
    created_at: datetime = Field(serialization_alias="createdAt")

    @classmethod
    def from_rows(cls, post_row: dict, file_rows: List[dict], author_row: dict) -> "PostResponse":
        """post_row + file_rows + author_row → 응답. 내부에서 model_validate 활용."""
        data = {
            **post_row,
            "author": author_row,
            "files": (file_rows or [])[:5],
        }
        return cls.model_validate(data)
