# app/posts/posts_schema.py
from pydantic import BaseModel, Field
from typing import Optional

# 게시글 작성 요청
class PostCreateRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=26, description="제목 (최대 26자)")
    content: str = Field(..., min_length=1, description="본문 (길이 제한 없음)")
    fileUrl: Optional[str] = Field(default="", description="파일 URL (선택)")

# 게시글 수정 요청
class PostUpdateRequest(BaseModel):
    title: Optional[str] = Field(default=None, min_length=1, max_length=26, description="제목 (최대 26자, 선택)")
    content: Optional[str] = Field(default=None, min_length=1, description="본문 (길이 제한 없음, 선택)")
    fileUrl: Optional[str] = Field(default=None, description="파일 URL (선택)")

# 게시글 이미지 업로드 응답
class PostImageUploadResponse(BaseModel):
    postFileUrl: str

# 저자 정보
class AuthorInfo(BaseModel):
    userId: int
    nickname: str
    profileImageUrl: str

# 파일 이미지 정보
class FileInfo(BaseModel):
    fileId: int
    fileUrl: str

# 게시글 목록조회 성공 응답
class PostResponse(BaseModel):
    postId: int
    title: str
    content: str
    hits: int
    likeCount: int
    commentCount: int
    author: AuthorInfo
    file: Optional[FileInfo]
    createdAt: str

# 게시글 상세조회 성공 응답
class PostDetailResponse(BaseModel):
    postId: int
    title: str
    content: str
    hits: int
    likeCount: int
    commentCount: int
    author: AuthorInfo
    file: Optional[FileInfo]
    createdAt: str
