# 이미지 업로드 응답 DTO. Image ORM → Controller에서 Schema로 직렬화.
from pydantic import Field

from app.common import BaseSchema


class ImageUploadResponse(BaseSchema):
    id: int
    file_url: str = Field(..., description="이미지 URL")


class SignupImageUploadData(BaseSchema):

    id: int
    file_url: str = Field(..., description="이미지 URL")
    signup_token: str = Field(..., description="회원가입 시 소유권 검증 토큰")
