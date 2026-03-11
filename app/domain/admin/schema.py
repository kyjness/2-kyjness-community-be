# 관리자 API 응답 DTO.

from app.common import BaseSchema, UtcDatetime


class UnblindedResponse(BaseSchema):
    unblinded: bool = True


class SuspendedResponse(BaseSchema):
    suspended: bool = True


class ReportedPostAuthorInfo(BaseSchema):
    id: int
    nickname: str
    profile_image_url: str | None = None


class ReportedPostItem(BaseSchema):
    id: int
    title: str
    user_id: int
    author: ReportedPostAuthorInfo | None = None
    report_count: int = 0
    is_blinded: bool = False
    created_at: UtcDatetime
