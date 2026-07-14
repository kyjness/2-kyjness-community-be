# 이미지 업로드 응답 DTO. Image ORM → Controller에서 Schema로 직렬화.
from typing import Literal

from pydantic import Field, field_validator

from app.common import BaseSchema, PublicId
from app.infra.storage import PRESIGNED_MAX_BYTES


class ImageUploadResponse(BaseSchema):
    id: PublicId
    file_url: str = Field(..., description="이미지 URL")


class SignupImageUploadData(BaseSchema):
    id: PublicId
    file_url: str = Field(..., description="이미지 URL")
    signup_token: str = Field(..., description="업로드 토큰 (Redis Upload Token)")


class PresignUploadRequest(BaseSchema):
    """S3 Presigned POST 발급 요청."""

    filename: str = Field(..., min_length=1, max_length=200, description="원본 파일명")
    content_type: str = Field(
        ...,
        description="업로드 Content-Type (image/jpeg, image/png, image/webp)",
    )


class PresignUploadResponse(BaseSchema):
    """S3 Presigned POST 발급 응답. 프론트는 url·fields로 multipart POST 후 confirm 호출."""

    url: str = Field(..., description="S3 POST URL")
    fields: dict[str, str] = Field(..., description="Presigned POST form fields")
    file_key: str = Field(..., description="pending/{uuid}/파일명 — confirm 시 동일 값 전달")


class ConfirmUploadRequest(BaseSchema):
    """클라이언트 S3 업로드 완료 후 영구 경로로 승격·DB 등록."""

    file_key: str = Field(..., min_length=1, max_length=255, description="presign 응답 file_key")
    purpose: Literal["profile", "post"] = Field("post", description="profile | post")
    size: int | None = Field(
        None,
        ge=1,
        le=PRESIGNED_MAX_BYTES,
        description="클라이언트가 측정한 바이트(선택, S3 HEAD와 교차 검증)",
    )

    @field_validator("file_key")
    @classmethod
    def file_key_not_empty(cls, v: str) -> str:
        k = v.strip().lstrip("/")
        if not k:
            raise ValueError("file_key must not be empty")
        return k


class ConfirmSignupUploadRequest(BaseSchema):
    """회원가입용 pending 업로드 확정."""

    file_key: str = Field(..., min_length=1, max_length=255)
    size: int | None = Field(None, ge=1, le=PRESIGNED_MAX_BYTES)

    @field_validator("file_key")
    @classmethod
    def file_key_not_empty(cls, v: str) -> str:
        k = v.strip().lstrip("/")
        if not k:
            raise ValueError("file_key must not be empty")
        return k
