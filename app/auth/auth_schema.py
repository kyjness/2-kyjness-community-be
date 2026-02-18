# app/auth/auth_schema.py
# DTO(Pydantic): 입력 형식 검증 책임. validators.py를 단일 소스로 사용.
from pydantic import BaseModel, EmailStr, Field, field_validator
from typing import Optional

from app.core.validators import ensure_password_format, ensure_nickname_format


# 회원가입 요청 바디. 프로필 이미지는 먼저 POST /v1/media/images 로 업로드 후 profileImageId 전달.
class SignUpRequest(BaseModel):
    """형식 검증은 DTO에서 수행. 컨트롤러는 검증된 값만 처리."""

    email: EmailStr = Field(..., description="사용자 이메일")
    password: str = Field(..., min_length=8, max_length=20, description="비밀번호 (8-20자, 대소문자+숫자+특수문자)")
    nickname: str = Field(..., min_length=1, max_length=10, description="닉네임 (1-10자, 한글/영/숫자)")
    profileImageId: Optional[int] = Field(default=None, description="프로필 이미지 ID (media 업로드 후 반환된 id, 선택)")

    @field_validator("password", mode="after")
    @classmethod
    def password_format(cls, v: str) -> str:
        return ensure_password_format(v)

    @field_validator("nickname", mode="after")
    @classmethod
    def nickname_format(cls, v: str) -> str:
        return ensure_nickname_format(v)


# 로그인 요청 바디
class LoginRequest(BaseModel):
    """형식 검증은 DTO에서 수행."""

    email: EmailStr = Field(..., description="사용자 이메일")
    password: str = Field(..., min_length=8, max_length=20, description="비밀번호 (8-20자)")

    @field_validator("password", mode="after")
    @classmethod
    def password_format(cls, v: str) -> str:
        return ensure_password_format(v)

# 로그인 성공 응답 데이터 (data 필드용)
class LoginData(BaseModel):
    userId: int
    email: str
    nickname: str
    profileImageUrl: str

# 로그인 상태 체크 응답 데이터
class MeData(BaseModel):
    userId: int
    email: str
    nickname: str
    profileImageUrl: str
