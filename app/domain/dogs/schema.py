# 강아지 프로필 요청/응답 DTO. 생년월일 검증은 상단 헬퍼 + Annotated로 응집.
from datetime import date
from typing import Annotated

from pydantic import AfterValidator, Field

from app.common import BaseSchema, DogGender, OptionalPublicId, PublicId

# --- 1. 상수 (없음) ---
# --- 2. 내부 헬퍼 ---


def _birth_date_not_future(v: date) -> date:
    if v > date.today():
        raise ValueError("강아지 생년월일은 오늘 이전이어야 합니다.")
    return v


# --- 3. Annotated 재사용 타입 ---
BirthDateNotFuture = Annotated[date, AfterValidator(_birth_date_not_future)]

# --- 4. 스키마 모델 ---


class DogProfileCreate(BaseSchema):
    name: str = Field(..., min_length=1, max_length=100)
    breed: str = Field(..., min_length=1, max_length=100)
    gender: DogGender = Field(...)
    birth_date: BirthDateNotFuture = Field(...)


class DogProfileResponse(BaseSchema):
    id: PublicId
    name: str
    breed: str
    gender: DogGender
    birth_date: date
    profile_image_id: OptionalPublicId = None
    profile_image_url: str | None = None
    is_representative: bool = False


class RepresentativeDogInfo(BaseSchema):
    name: str
    breed: str
    gender: DogGender
    birth_date: date


class DogProfileUpsertItem(BaseSchema):
    id: OptionalPublicId = Field(default=None, description="있으면 수정, 없으면 생성")
    name: str = Field(..., min_length=1, max_length=100)
    breed: str = Field(..., min_length=1, max_length=100)
    gender: DogGender = Field(...)
    birth_date: BirthDateNotFuture = Field(...)
    profile_image_id: OptionalPublicId = None
    is_representative: bool = False


class SetRepresentativeDogRequest(BaseSchema):
    dog_id: PublicId = Field(..., description="대표로 지정할 강아지 ID (Base62)")
