# 신고 API. POST /reports (로그인 필수).
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import CurrentUser, get_current_user, get_master_db
from app.common import ApiCode, ApiResponse
from app.reports.schema import ReportCreateRequest, ReportSubmitData
from app.reports.service import ReportService

router = APIRouter(prefix="/reports", tags=["reports"])


@router.post("", status_code=201, response_model=ApiResponse[ReportSubmitData])
async def create_report(
    data: ReportCreateRequest,
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_master_db),
):
    result = await ReportService.submit_report(user.id, data, db=db)
    return ApiResponse(code=ApiCode.REPORT_SUBMITTED.value, data=result)
