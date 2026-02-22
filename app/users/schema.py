# app/users/schema.py

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field, field_validator, model_validator

from app.core.validators import ensure_password_format, ensure_nickname_format


class UserAvailabilityQuery(BaseModel):
    email: Optional[str] = None
    nickname: Optional[str] = None

    @field_validator("email", "nickname", mode="before")
    @classmethod
    def strip_empty_to_none(cls, v):
        if v is None:
            return None
        if isinstance(v, str):
            return v.strip() or None
        return v

    @model_validator(mode="after")
    def at_least_one(self):
        if not (self.email or self.nickname):
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
        if v is None:
            return None
        if isinstance(v, str):
            return v.strip() or None
        return v

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
    id: int = Field(serialization_alias="userId")
    email: str
    nickname: str
    profile_image_url: str = Field(serialization_alias="profileImageUrl", default="")
    created_at: datetime = Field(serialization_alias="createdAt")

    @field_validator("profile_image_url", mode="before")
    @classmethod
    def empty_str_if_none(cls, v):
        return (v or "").strip() or ""
