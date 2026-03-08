from typing import Optional

from pydantic import EmailStr, Field, field_validator, model_validator

from app.common import (
    BaseSchema,
    UserStatus,
    ensure_nickname_format,
    ensure_password_format,
)


class SignUpRequest(BaseSchema):
    email: EmailStr = Field(..., description="사용자 이메일")
    password: str = Field(
        ..., min_length=8, max_length=20, description="비밀번호 (8-20자)"
    )
    nickname: str = Field(
        ..., min_length=1, max_length=10, description="닉네임 (1-10자)"
    )
    profile_image_id: Optional[int] = Field(
        default=None, description="프로필 이미지 ID"
    )
    signup_token: Optional[str] = Field(
        default=None, description="프로필 이미지 소유권 검증 토큰"
    )

    @model_validator(mode="after")
    def profile_image_requires_token(self):
        if self.profile_image_id is not None and not self.signup_token:
            raise ValueError("profileImageId 사용 시 signupToken이 필요합니다.")
        if self.signup_token and self.profile_image_id is None:
            raise ValueError("signupToken은 profileImageId와 함께 보내야 합니다.")
        return self

    @field_validator("password", mode="after")
    @classmethod
    def password_format(cls, v: str) -> str:
        return ensure_password_format(v)

    @field_validator("nickname", mode="after")
    @classmethod
    def nickname_format(cls, v: str) -> str:
        return ensure_nickname_format(v)


class LoginRequest(BaseSchema):
    email: EmailStr = Field(...)
    password: str = Field(..., min_length=8, max_length=20)

    @field_validator("password", mode="after")
    @classmethod
    def password_format(cls, v: str) -> str:
        return ensure_password_format(v)


class LoginSuccessData(BaseSchema):
    id: int
    email: str
    nickname: str
    status: UserStatus = UserStatus.ACTIVE
    profile_image_id: Optional[int] = None
    profile_image_url: Optional[str] = None
    access_token: str


class AccessTokenData(BaseSchema):
    access_token: str
