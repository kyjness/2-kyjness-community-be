# 신고 요청/응답 DTO.
from pydantic import Field

from app.common import BaseSchema
from app.common.enums import ReportReason, TargetType


class ReportCreateRequest(BaseSchema):
    target_type: TargetType = Field(..., description="신고 대상: POST(게시글) | COMMENT(댓글)")
    target_id: str = Field(
        ..., min_length=26, max_length=26, description="대상 ID (게시글 또는 댓글 ULID)"
    )
    reason: ReportReason = Field(..., description="신고 사유 (스팸|욕설|부적절한 콘텐츠|기타)")


class ReportSubmitData(BaseSchema):
    reported: bool = True
    blinded: bool = Field(default=False, description="이번 신고로 5회 달성해 블라인드 처리됨")
