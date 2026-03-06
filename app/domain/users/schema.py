# 사용자 요청/응답 DTO. UserUpdateRequest, UserResponse, PasswordUpdateRequest 등.
from datetime import date
from typing import List, Optional

from pydantic import Field, field_validator, model_validator

from app.common import BaseSchema, DogGender, UserStatus, ensure_nickname_format, ensure_password_format, UtcDatetime


# ----- 강아지 프로필 스키마 -----


class DogProfileCreate(BaseSchema):
    name: str = Field(..., min_length=1, max_length=100)
    breed: str = Field(..., min_length=1, max_length=100)
    gender: DogGender = Field(...)
    birth_date: date = Field(...)


class DogProfileResponse(BaseSchema):
    id: int
    name: str
    breed: str
    gender: DogGender
    birth_date: date
    profile_image_id: Optional[int] = None
    profile_image_url: Optional[str] = None
    is_representative: bool = False


class RepresentativeDogInfo(BaseSchema):
    name: str
    breed: str
    gender: DogGender
    birth_date: date


class DogProfileUpsertItem(BaseSchema):
    id: Optional[int] = Field(default=None, description="있으면 수정, 없으면 생성")
    name: str = Field(..., min_length=1, max_length=100)
    breed: str = Field(..., min_length=1, max_length=100)
    gender: DogGender = Field(...)
    birth_date: date = Field(...)
    profile_image_id: Optional[int] = None
    is_representative: bool = False


class AvailabilityData(BaseSchema):

    email_available: Optional[bool] = None
    nickname_available: Optional[bool] = None


class UserAvailabilityQuery(BaseSchema):
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


class UpdateUserRequest(BaseSchema):
    nickname: Optional[str] = Field(default=None)
    profile_image_id: Optional[int] = Field(default=None, description="null이면 프로필 이미지 제거")
    clear_profile_image: bool = Field(default=False, description="프로필 이미지 강제 삭제 플래그 (camelCase: clearProfileImage)")
    dogs: Optional[List[DogProfileUpsertItem]] = Field(default=None, description="강아지 목록 전체 교체(생성/수정/삭제 반영)")

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
        has_nickname = self.nickname is not None
        has_profile_image_field = "profile_image_id" in self.model_fields_set
        has_dogs = self.dogs is not None
        if has_nickname or has_profile_image_field or has_dogs or self.clear_profile_image:
            return self
        raise ValueError("MISSING_REQUIRED_FIELD")

    @field_validator("nickname", mode="after")
    @classmethod
    def nickname_format(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        return ensure_nickname_format(v)


class UpdatePasswordRequest(BaseSchema):
    current_password: str = Field(..., min_length=1)
    new_password: str = Field(..., min_length=1)

    @field_validator("new_password", mode="after")
    @classmethod
    def new_password_format(cls, v: str) -> str:
        return ensure_password_format(v)


class UserProfileResponse(BaseSchema):
    id: int
    email: str
    nickname: str
    status: UserStatus = Field(..., description="ACTIVE|BANNED|DELETED")
    profile_image_id: Optional[int] = None
    profile_image_url: Optional[str] = None
    created_at: UtcDatetime
    dogs: List[DogProfileResponse] = Field(default_factory=list, description="등록된 강아지 목록")
    representative_dog: Optional["RepresentativeDogInfo"] = Field(default=None, description="대표 강아지(1마리), 없으면 null")
