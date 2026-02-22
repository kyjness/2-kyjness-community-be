# app/auth/schema.py

from typing import Optional

from pydantic import BaseModel, EmailStr, Field, field_validator

from app.core.validators import ensure_password_format, ensure_nickname_format


class SignUpRequest(BaseModel):
    email: EmailStr = Field(..., description="사용자 이메일")
    password: str = Field(..., min_length=8, max_length=20, description="비밀번호 (8-20자)")
    nickname: str = Field(..., min_length=1, max_length=10, description="닉네임 (1-10자)")
    profileImageId: Optional[int] = Field(default=None, description="프로필 이미지 ID")

    @field_validator("password", mode="after")
    @classmethod
    def password_format(cls, v: str) -> str:
        return ensure_password_format(v)

    @field_validator("nickname", mode="after")
    @classmethod
    def nickname_format(cls, v: str) -> str:
        return ensure_nickname_format(v)


class LoginRequest(BaseModel):
    email: EmailStr = Field(...)
    password: str = Field(..., min_length=8, max_length=20)

    @field_validator("password", mode="after")
    @classmethod
    def password_format(cls, v: str) -> str:
        return ensure_password_format(v)


class LoginResponse(BaseModel):
    id: int = Field(serialization_alias="userId")
    email: str
    nickname: str
    profile_image_url: str = Field(serialization_alias="profileImageUrl", default="")

    @field_validator("profile_image_url", mode="before")
    @classmethod
    def empty_str_if_none(cls, v):
        return (v or "").strip() or ""


class SessionUserResponse(BaseModel):
    id: int = Field(serialization_alias="userId")
    email: str
    nickname: str
    profile_image_url: str = Field(serialization_alias="profileImageUrl", default="")

    @field_validator("profile_image_url", mode="before")
    @classmethod
    def empty_str_if_none(cls, v):
        return (v or "").strip() or ""
