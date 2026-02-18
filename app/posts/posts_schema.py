# app/posts/posts_schema.py
from pydantic import BaseModel, Field, field_validator
from typing import List, Optional


# 게시글 작성 요청. 이미지는 먼저 POST /v1/media/images 로 업로드 후 imageIds 전달 (최대 5개).
class PostCreateRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=26, description="제목 (최대 26자)")
    content: str = Field(..., min_length=1, description="본문 (길이 제한 없음)")
    imageIds: Optional[List[int]] = Field(default=None, max_length=5, description="이미지 ID 목록 (최대 5개, media 업로드 후 반환된 id)")

    @field_validator("imageIds")
    @classmethod
    def image_ids_max_five(cls, v: Optional[List[int]]) -> Optional[List[int]]:
        if v is not None and len(v) > 5:
            raise ValueError("POST_FILE_LIMIT_EXCEEDED")
        return v


# 게시글 수정 요청
class PostUpdateRequest(BaseModel):
    title: Optional[str] = Field(default=None, min_length=1, max_length=26, description="제목 (최대 26자, 선택)")
    content: Optional[str] = Field(default=None, min_length=1, description="본문 (길이 제한 없음, 선택)")
    imageIds: Optional[List[int]] = Field(default=None, description="이미지 ID 목록 (최대 5개, 지정 시 기존 이미지 교체)")

    @field_validator("imageIds")
    @classmethod
    def image_ids_max_five(cls, v: Optional[List[int]]) -> Optional[List[int]]:
        if v is not None and len(v) > 5:
            raise ValueError("POST_FILE_LIMIT_EXCEEDED")
        return v

# 저자 정보
class AuthorInfo(BaseModel):
    userId: int
    nickname: str
    profileImageUrl: str

# 파일 이미지 정보 (최대 5장). imageId는 수정 시 기존 이미지 유지용으로 응답에 포함
class FileInfo(BaseModel):
    fileId: int
    fileUrl: str
    imageId: Optional[int] = None

# 게시글 목록/상세 공통 응답 (data 필드용)
class PostResponse(BaseModel):
    postId: int
    title: str
    content: str
    hits: int
    likeCount: int
    commentCount: int
    author: AuthorInfo
    files: List[FileInfo] = Field(default_factory=list, description="이미지 목록 (최대 5장)")
    createdAt: str
