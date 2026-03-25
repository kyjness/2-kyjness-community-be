from pydantic import EmailStr, Field, model_validator

from app.common import BaseSchema, UserStatus
from app.users.schema import NicknameStr, PasswordStr


class SignUpRequest(BaseSchema):
    email: EmailStr = Field(..., description="사용자 이메일")
    password: PasswordStr = Field(..., min_length=8, max_length=20, description="비밀번호 (8-20자)")
    nickname: NicknameStr = Field(..., min_length=1, max_length=10, description="닉네임 (1-10자)")
    profile_image_id: int | None = None
    signup_token: str | None = Field(default=None, description="업로드 토큰 (Redis Upload Token)")

    @model_validator(mode="after")
    def profile_image_requires_token(self) -> "SignUpRequest":
        if self.profile_image_id is not None and not self.signup_token:
            raise ValueError("profileImageId 사용 시 signupToken이 필요합니다.")
        return self


class LoginRequest(BaseSchema):
    email: EmailStr = Field(...)
    password: PasswordStr = Field(..., min_length=8, max_length=20)


class LoginSuccessData(BaseSchema):
    id: int
    email: str
    nickname: str
    status: UserStatus = UserStatus.ACTIVE
    profile_image_id: int | None = None
    profile_image_url: str | None = None
    access_token: str


class AccessTokenData(BaseSchema):
    access_token: str
