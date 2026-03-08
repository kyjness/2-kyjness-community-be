# 강아지 프로필 요청/응답 DTO. ApiCode 미참조(순수 ValueError).
from datetime import date
from typing import Optional

from pydantic import Field, field_validator

from app.common import BaseSchema, DogGender


def _birth_date_not_future(v: date) -> date:
    if v > date.today():
        raise ValueError("강아지 생년월일은 오늘 이전이어야 합니다.")
    return v


class DogProfileCreate(BaseSchema):
    name: str = Field(..., min_length=1, max_length=100)
    breed: str = Field(..., min_length=1, max_length=100)
    gender: DogGender = Field(...)
    birth_date: date = Field(...)

    _birth_date_valid = field_validator("birth_date")(_birth_date_not_future)


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

    _birth_date_valid = field_validator("birth_date")(_birth_date_not_future)


class SetRepresentativeDogRequest(BaseSchema):
    dog_id: int = Field(..., gt=0, description="대표로 지정할 강아지 ID")
