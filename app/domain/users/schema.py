# 사용자 요청/응답 DTO. UserUpdateRequest, UserResponse, PasswordUpdateRequest 등.
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.common import ensure_nickname_format, ensure_password_format


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
    profile_image_id: Optional[int] = Field(default=None, validation_alias="profileImageId", serialization_alias="profileImageId")

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
        if self.nickname is None and self.profile_image_id is None:
            raise ValueError("MISSING_REQUIRED_FIELD")
        return self

    @field_validator("nickname", mode="after")
    @classmethod
    def nickname_format(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        return ensure_nickname_format(v)


class UpdatePasswordRequest(BaseModel):
    current_password: str = Field(..., min_length=1, validation_alias="currentPassword", serialization_alias="currentPassword")
    new_password: str = Field(..., validation_alias="newPassword", serialization_alias="newPassword")

    @field_validator("new_password", mode="after")
    @classmethod
    def new_password_format(cls, v: str) -> str:
        return ensure_password_format(v)


class UserProfileResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int = Field(serialization_alias="userId")
    email: str
    nickname: str
    profile_image_id: Optional[int] = Field(default=None, serialization_alias="profileImageId")
    profile_image_url: Optional[str] = Field(default=None, serialization_alias="profileImageUrl")
    created_at: datetime = Field(serialization_alias="createdAt")
