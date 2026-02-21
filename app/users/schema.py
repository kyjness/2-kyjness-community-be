# app/users/schema.py
"""요청/응답 DTO."""

from typing import Optional

from pydantic import BaseModel, Field, field_validator, model_validator

from app.core.validators import ensure_password_format, ensure_nickname_format


def _strip_empty_to_none(v):
    if v is None:
        return None
    if isinstance(v, str):
        return v.strip() or None
    return v


class UserAvailabilityQuery(BaseModel):
    email: Optional[str] = None
    nickname: Optional[str] = None

    @field_validator("email", "nickname", mode="before")
    @classmethod
    def strip_empty_to_none(cls, v):
        return _strip_empty_to_none(v)

    @model_validator(mode="after")
    def at_least_one(self):
        if self.email is None and self.nickname is None:
            raise ValueError("INVALID_REQUEST")
        if not self.email and not self.nickname:
            raise ValueError("INVALID_REQUEST")
        return self

    @model_validator(mode="after")
    def nickname_format_when_provided(self):
        if self.nickname:
            ensure_nickname_format(self.nickname)
        return self


class UpdateUserRequest(BaseModel):
    nickname: Optional[str] = Field(default=None)
    profileImageId: Optional[int] = Field(default=None)

    @field_validator("nickname", mode="before")
    @classmethod
    def strip_empty_to_none(cls, v):
        return _strip_empty_to_none(v)

    @model_validator(mode="after")
    def at_least_one(self):
        if self.nickname is None and self.profileImageId is None:
            raise ValueError("MISSING_REQUIRED_FIELD")
        return self

    @field_validator("nickname", mode="after")
    @classmethod
    def nickname_format(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        return ensure_nickname_format(v)


class UpdatePasswordRequest(BaseModel):
    currentPassword: str = Field(..., min_length=1)
    newPassword: str = Field(...)

    @field_validator("newPassword", mode="after")
    @classmethod
    def new_password_format(cls, v: str) -> str:
        return ensure_password_format(v)


class UserProfileResponse(BaseModel):
    """GET /users/me 전용."""
    userId: int
    email: str
    nickname: str
    profileImageUrl: str
    createdAt: str
