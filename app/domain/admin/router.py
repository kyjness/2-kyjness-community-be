# 관리자 전용 API. 모든 엔드포인트 Depends(get_current_admin).
from fastapi import APIRouter, Depends, Path, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.admin.schema import (
    ReportedPostItem,
    SuspendedResponse,
    UnblindedResponse,
)
from app.admin.service import AdminService
from app.api.dependencies import CurrentUser, get_current_admin, get_master_db
from app.common import ApiCode, ApiResponse, PaginatedResponse

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get(
    "/reported-posts",
    status_code=200,
    response_model=ApiResponse[PaginatedResponse[ReportedPostItem]],
)
async def get_reported_posts(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    admin: CurrentUser = Depends(get_current_admin),
    db: AsyncSession = Depends(get_master_db),
):
    items, total = await AdminService.get_reported_posts(page=page, size=size, db=db)
    has_more = (page * size) < total
    return ApiResponse(
        code=ApiCode.OK.value,
        data=PaginatedResponse(items=items, has_more=has_more, total=total),
    )


@router.patch(
    "/posts/{post_id}/unblind",
    status_code=200,
    response_model=ApiResponse[UnblindedResponse],
)
async def unblind_post(
    post_id: int = Path(..., ge=1),
    admin: CurrentUser = Depends(get_current_admin),
    db: AsyncSession = Depends(get_master_db),
):
    await AdminService.unblind_post(post_id, db=db)
    return ApiResponse(code=ApiCode.OK.value, data=UnblindedResponse())


@router.patch(
    "/users/{user_id}/suspend",
    status_code=200,
    response_model=ApiResponse[SuspendedResponse],
)
async def suspend_user(
    user_id: int = Path(..., ge=1),
    admin: CurrentUser = Depends(get_current_admin),
    db: AsyncSession = Depends(get_master_db),
):
    await AdminService.suspend_user(user_id, db=db)
    return ApiResponse(code=ApiCode.OK.value, data=SuspendedResponse())


@router.delete(
    "/posts/{post_id}",
    status_code=200,
    response_model=ApiResponse[None],
)
async def delete_post_admin(
    post_id: int = Path(..., ge=1),
    admin: CurrentUser = Depends(get_current_admin),
    db: AsyncSession = Depends(get_master_db),
):
    await AdminService.delete_post(post_id, db=db)
    return ApiResponse(code=ApiCode.POST_DELETED.value, data=None)
