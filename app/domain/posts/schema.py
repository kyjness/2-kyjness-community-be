# 게시글 요청/응답 DTO. 이미지 개수 제한 검증은 상단 헬퍼 + Annotated로 응집.
from typing import Annotated

from pydantic import AfterValidator, Field, field_validator, model_validator

from app.common import BaseSchema, UserStatus, UtcDatetime
from app.common.codes import ApiCode
from app.users.schema import RepresentativeDogInfo

# --- 1. 상수 (없음) ---
# --- 2. 내부 헬퍼 ---


def _image_ids_max_five(v: list[int] | None) -> list[int] | None:
    if v is not None and len(v) > 5:
        raise ValueError(ApiCode.POST_FILE_LIMIT_EXCEEDED.name)
    return v


# --- 3. Annotated 재사용 타입 ---
ImageIdsMaxFive = Annotated[list[int] | None, AfterValidator(_image_ids_max_five)]

# --- 4. 스키마 모델 ---


class PostIdData(BaseSchema):
    id: int


class PostCreateRequest(BaseSchema):
    title: str = Field(..., min_length=1, max_length=26)
    content: str = Field(..., min_length=1, max_length=50_000)
    image_ids: ImageIdsMaxFive = None
    category_id: int | None = None
    hashtags: list[str] | None = None


class PostUpdateRequest(BaseSchema):
    title: str | None = Field(default=None, min_length=1, max_length=26)
    content: str | None = Field(default=None, min_length=1, max_length=50_000)
    image_ids: ImageIdsMaxFive = None
    category_id: int | None = None
    hashtags: list[str] | None = None


class AuthorInfo(BaseSchema):
    id: int
    nickname: str
    profile_image_id: int | None = None
    profile_image_url: str | None = None
    representative_dog: RepresentativeDogInfo | None = None

    @model_validator(mode="wrap")
    @classmethod
    def anonymize_inactive(cls, data, handler):
        status = getattr(data, "status", None)
        if status is not None and not UserStatus.is_active_value(status):
            if hasattr(data, "id"):
                return handler(
                    {
                        "id": data.id,
                        "nickname": "알수없음",
                        "profile_image_id": None,
                        "profile_image_url": None,
                        "representative_dog": None,
                    }
                )
        return handler(data)


class FileInfo(BaseSchema):
    id: int
    file_url: str | None = None
    image_id: int | None = None


class PostResponse(BaseSchema):
    id: int
    title: str
    content: str
    view_count: int = 0
    like_count: int = 0
    comment_count: int = 0
    is_liked: bool = False
    author: AuthorInfo
    files: list[FileInfo] = Field(default_factory=list)
    category_id: int | None = None
    hashtags: list[str] = Field(default_factory=list)
    created_at: UtcDatetime

    @field_validator("hashtags", mode="before")
    @classmethod
    def _hashtags_from_entities(cls, v: object):
        # ORM에서 Post.hashtags는 Hashtag 엔티티 리스트이므로 이름만 추출.
        if v is None:
            return []
        if isinstance(v, list):
            if not v:
                return []
            if isinstance(v[0], str):
                return v
            return [getattr(x, "name", str(x)) for x in v]
        return v
