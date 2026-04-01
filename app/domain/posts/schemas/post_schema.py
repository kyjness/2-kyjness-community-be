from typing import Annotated

from pydantic import AfterValidator, Field, computed_field, field_validator, model_validator

from app.common import BaseSchema, UserStatus, UtcDatetime
from app.common.codes import ApiCode
from app.users.schema import RepresentativeDogInfo

_POST_HASHTAGS_MAX = 6


def _image_ids_max_five(v: list[str] | None) -> list[str] | None:
    if v is not None and len(v) > 5:
        raise ValueError(ApiCode.POST_FILE_LIMIT_EXCEEDED.name)
    return v


def _hashtags_max_six(v: list[str] | None) -> list[str] | None:
    if v is not None and len(v) > _POST_HASHTAGS_MAX:
        raise ValueError(ApiCode.POST_HASHTAG_LIMIT_EXCEEDED.name)
    return v


ImageIdsMaxFive = Annotated[list[str] | None, AfterValidator(_image_ids_max_five)]
HashtagsMaxSix = Annotated[list[str] | None, AfterValidator(_hashtags_max_six)]


class PostIdData(BaseSchema):
    id: str


class PostCreateRequest(BaseSchema):
    title: str = Field(..., min_length=1, max_length=26)
    content: str = Field(..., min_length=1, max_length=50_000)
    image_ids: ImageIdsMaxFive = None
    category_id: int | None = None
    hashtags: HashtagsMaxSix = None


class PostUpdateRequest(BaseSchema):
    title: str | None = Field(default=None, min_length=1, max_length=26)
    content: str | None = Field(default=None, min_length=1, max_length=50_000)
    image_ids: ImageIdsMaxFive = None
    category_id: int | None = None
    hashtags: HashtagsMaxSix = None
    version: int | None = Field(
        default=None,
        description="낙관적 락: 직전 GET 응답의 version과 일치해야 수정 성공",
    )


class AuthorInfo(BaseSchema):
    id: str
    nickname: str
    profile_image_id: str | None = None
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
    id: str
    file_url: str | None = None
    image_id: str | None = None


class PostResponse(BaseSchema):
    id: str
    title: str
    content: str
    view_count: int = 0
    like_count: int = 0
    comment_count: int = 0
    is_liked: bool = False
    author: AuthorInfo | None = None
    files: list[FileInfo] = Field(default_factory=list)
    category_id: int | None = None
    hashtags: list[str] = Field(default_factory=list)
    version: int = 1
    created_at: UtcDatetime

    @computed_field
    @property
    def is_edited(self) -> bool:
        return self.version > 1

    @field_validator("hashtags", mode="before")
    @classmethod
    def _hashtags_from_entities(cls, v: object):
        if v is None:
            return []
        if isinstance(v, list):
            if not v:
                return []
            if isinstance(v[0], str):
                return v
            return [getattr(x, "name", str(x)) for x in v]
        return v
