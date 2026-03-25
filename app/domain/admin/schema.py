# 관리자 API 응답 DTO.

from app.common import BaseSchema, UtcDatetime


class UnblindedResponse(BaseSchema):
    unblinded: bool = True


class ResetReportsResponse(BaseSchema):
    reset: bool = True


class SuspendedResponse(BaseSchema):
    suspended: bool = True


class ActivatedResponse(BaseSchema):
    activated: bool = True


class BlindedResponse(BaseSchema):
    blinded: bool = True


class MediaSweepResponse(BaseSchema):
    sweep_started: bool = True


class ReportedPostAuthorInfo(BaseSchema):
    id: int
    nickname: str
    profile_image_url: str | None = None
    status: str | None = None  # ACTIVE, SUSPENDED 등 (배지·토글용)


class ReportedPostItem(BaseSchema):
    target_type: str  # "POST" | "COMMENT"
    id: int  # post_id (POST) or comment_id (COMMENT)
    post_id: int  # 게시글 상세 링크용 (POST면 id와 동일, COMMENT면 댓글이 달린 글 id)
    title: str  # 게시글 제목 (POST=해당 글 제목, COMMENT=댓글이 달린 글 제목)
    content_preview: str = ""  # 내용 일부 (POST=게시글 본문, COMMENT=댓글 내용)
    user_id: int
    author: ReportedPostAuthorInfo | None = None
    author_status: str | None = None  # ACTIVE, SUSPENDED
    report_count: int = 0
    report_reasons: list[str] = []
    is_blinded: bool = False
    created_at: UtcDatetime
    last_reported_at: UtcDatetime | None = None
