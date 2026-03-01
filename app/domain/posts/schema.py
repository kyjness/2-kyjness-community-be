# 게시글 요청/응답 DTO. PostCreateRequest, PostResponse, 피드·상세 스키마.
from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


class PostCreateRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=26)
    content: str = Field(..., min_length=1)
    image_ids: Optional[List[int]] = Field(default=None, max_length=5, validation_alias="imageIds", serialization_alias="imageIds")

    @field_validator("image_ids")
    @classmethod
    def image_ids_max_five_create(cls, v: Optional[List[int]]) -> Optional[List[int]]:
        if v is not None and len(v) > 5:
            raise ValueError("POST_FILE_LIMIT_EXCEEDED")
        return v


class PostUpdateRequest(BaseModel):
    title: Optional[str] = Field(default=None, min_length=1, max_length=26)
    content: Optional[str] = Field(default=None, min_length=1)
    image_ids: Optional[List[int]] = Field(default=None, validation_alias="imageIds", serialization_alias="imageIds")

    @field_validator("image_ids")
    @classmethod
    def image_ids_max_five_update(cls, v: Optional[List[int]]) -> Optional[List[int]]:
        if v is not None and len(v) > 5:
            raise ValueError("POST_FILE_LIMIT_EXCEEDED")
        return v


class AuthorInfo(BaseModel):
    model_config = {"from_attributes": True}

    id: int = Field(serialization_alias="userId")
    nickname: str
    profile_image_id: Optional[int] = Field(default=None, serialization_alias="profileImageId")
    profile_image_url: Optional[str] = Field(default=None, serialization_alias="profileImageUrl")


class FileInfo(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int = Field(serialization_alias="fileId")
    file_url: Optional[str] = Field(default=None, serialization_alias="fileUrl")
    image_id: Optional[int] = Field(default=None, serialization_alias="imageId")


class PostListQuery(BaseModel):
    """목록 쿼리. 추후 필터/정렬/검색 기능 추가 시 필드 확장용. 라우터에서는 현재 Query()로 직접 받음."""
    page: int = Field(1, ge=1, description="페이지 번호")
    size: int = Field(10, ge=1, le=100, description="페이지 크기 (기본 10, 최대 100)")


class PostListResponse(BaseModel):
    id: int = Field(serialization_alias="postId")
    title: str
    content_preview: str = Field(serialization_alias="contentPreview")
    view_count: int = Field(serialization_alias="hits", default=0)
    like_count: int = Field(serialization_alias="likeCount", default=0)
    comment_count: int = Field(serialization_alias="commentCount", default=0)
    author: AuthorInfo
    files: List[FileInfo] = Field(default_factory=list)
    created_at: datetime = Field(serialization_alias="createdAt")


class PostResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int = Field(serialization_alias="postId")
    title: str
    content: str
    view_count: int = Field(serialization_alias="hits", default=0)
    like_count: int = Field(serialization_alias="likeCount", default=0)
    comment_count: int = Field(serialization_alias="commentCount", default=0)
    author: AuthorInfo
    files: List[FileInfo] = Field(default_factory=list)
    created_at: datetime = Field(serialization_alias="createdAt")

    @field_validator("files", mode="before")
    @classmethod
    def files_from_orm(cls, v):
        if v is None:
            return []
        if not isinstance(v, list):
            return v
        if not v:
            return []
        first = v[0]
        if isinstance(first, dict):
            return [FileInfo(**d) for d in v]
        return [FileInfo.model_validate(pi) for pi in v]
