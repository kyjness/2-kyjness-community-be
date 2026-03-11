# 신고 요청/응답 DTO.
from typing import Literal

from pydantic import Field

from app.common import BaseSchema


class ReportCreateRequest(BaseSchema):
    target_type: Literal["POST", "COMMENT"] = Field(..., description="신고 대상 유형")
    target_id: int = Field(..., ge=1, description="대상 ID (게시글 또는 댓글 PK)")
    reason: str | None = Field(default=None, max_length=500)


class ReportSubmitData(BaseSchema):
    reported: bool = True
    blinded: bool = Field(default=False, description="이번 신고로 5회 달성해 블라인드 처리됨")
