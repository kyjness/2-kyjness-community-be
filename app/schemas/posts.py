from pydantic import BaseModel, Field, field_validator
from typing import Optional

#게시글 작성 요청
class PostCreateRequest(BaseModel):
    title: str = Field(..., min_length=1)
    content: str = Field(..., min_length=1)
    fileUrl: Optional[str] = Field(default="")

    @field_validator('title')
    @classmethod
    def validate_title(cls, v):
        if not v or not v.strip():
            raise ValueError('INVALID_TITLE_FORMAT')
        return v

    @field_validator('content')
    @classmethod
    def validate_content(cls, v):
        if not v or not v.strip():
            raise ValueError('INVALID_CONTENT_FORMAT')
        return v

    @field_validator('fileUrl')
    @classmethod
    def validate_file_url(cls, v):
        if v and not (v.startswith("http://") or v.startswith("https://") or v.startswith("{BE-API-URL}")):
            raise ValueError('INVALID_FILEURL')
        return v

#게시글 수정 요청
class PostUpdateRequest(BaseModel):
    title: Optional[str] = Field(default=None)
    content: Optional[str] = Field(default=None)
    fileUrl: Optional[str] = Field(default=None)

    @field_validator('title')
    @classmethod
    def validate_title(cls, v):
        if v is not None and (not v or not v.strip()):
            raise ValueError('INVALID_TITLE_FORMAT')
        return v

    @field_validator('content')
    @classmethod
    def validate_content(cls, v):
        if v is not None and (not v or not v.strip()):
            raise ValueError('INVALID_CONTENT_FORMAT')
        return v

    @field_validator('fileUrl')
    @classmethod
    def validate_file_url(cls, v):
        if v and not (v.startswith("http://") or v.startswith("https://") or v.startswith("{BE-API-URL}")):
            raise ValueError('INVALID_FILEURL')
        return v

#게시글 이미지 업로드 요청
class PostImageUploadResponse(BaseModel):
    postFileUrl: str

#저자 정보
class AuthorInfo(BaseModel):
    userId: int
    nickname: str
    profileImageUrl: str

#파일 이미지 정보
class FileInfo(BaseModel):
    fileId: int
    fileUrl: str

#게시글 목록조회 성공 응답
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

#게시글 상세조회 성공 응답
class PostListResponse(BaseModel):
    postId: int
    title: str
    content: str
    hits: int
    likeCount: int
    commentCount: int
    author: AuthorInfo
    createdAt: str