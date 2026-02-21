# app/users/users_schema.py
# DTO(Pydantic): 입력 존재 여부·타입·형식 검증. validators.py(ensure_*) 단일 소스.
# 전처리(strip→None)로 model_validator 단순화, 길이/형식은 ensure_*에서만 검증하여 에러코드 일관.
from pydantic import BaseModel, Field, field_validator, model_validator
from typing import Optional

from app.core.validators import ensure_password_format, ensure_nickname_format


def _strip_empty_to_none(v):
    """공백 문자열을 None으로 통일. 전처리용."""
    if v is None:
        return None
    if isinstance(v, str):
        return v.strip() or None
    return v


# --- GET /v1/users/availability (이메일·닉네임 가용 여부) Query DTO ---
class UserAvailabilityQuery(BaseModel):
    """email, nickname 중 최소 하나는 비어 있지 않아야 함. 닉네임 형식은 ensure_*로 검증."""
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


# --- PATCH /users/me (내 정보 수정) Body DTO ---
class UpdateUserRequest(BaseModel):
    """닉네임 또는 profileImageId 중 최소 하나 필수. 프로필 이미지는 미리 POST /v1/media/images 로 업로드 후 id 전달."""
    nickname: Optional[str] = Field(default=None, description="닉네임 (1~10자 한글/영/숫자)")
    profileImageId: Optional[int] = Field(default=None, description="프로필 이미지 ID (media 업로드 후 반환된 id)")

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


# --- PATCH /users/me/password (비밀번호 변경) Body DTO ---
class UpdatePasswordRequest(BaseModel):
    """currentPassword는 검증 생략(현업 관례). newPassword만 ensure_password_format 적용."""
    currentPassword: str = Field(..., min_length=1, description="현재 비밀번호")
    newPassword: str = Field(..., description="새 비밀번호 (8~20자, 대소문자+숫자+특수문자)")

    @field_validator("newPassword", mode="after")
    @classmethod
    def new_password_format(cls, v: str) -> str:
        return ensure_password_format(v)

# 내 프로필 조회 응답 (GET /users/me data 필드용)
class UserProfileResponse(BaseModel):
    userId: int
    email: str
    nickname: str
    profileImageUrl: str
    createdAt: str

