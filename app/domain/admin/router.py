# 관리자 전용 API. 모든 엔드포인트 Depends(get_current_admin).
from fastapi import APIRouter, Depends, Path, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.admin.schema import (
    ActivatedResponse,
    BlindedResponse,
    ReportedPostItem,
    ResetReportsResponse,
    SuspendedResponse,
    UnblindedResponse,
)
from app.admin.service import AdminService
from app.api.dependencies import CurrentUser, get_current_admin, get_master_db
from app.common import ApiCode, ApiResponse, PaginatedResponse, api_response

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get(
    "/reported-posts",
    status_code=200,
    response_model=ApiResponse[PaginatedResponse[ReportedPostItem]],
)
async def get_reported_posts(
    request: Request,
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    admin: CurrentUser = Depends(get_current_admin),
    db: AsyncSession = Depends(get_master_db),
):
    items, total = await AdminService.get_reported_posts(page=page, size=size, db=db)
    has_more = (page * size) < total
    return api_response(
        request,
        code=ApiCode.OK,
        data=PaginatedResponse(items=items, has_more=has_more, total=total),
    )


@router.patch(
    "/posts/{post_id}/unblind",
    status_code=200,
    response_model=ApiResponse[UnblindedResponse],
)
async def unblind_post(
    request: Request,
    post_id: int = Path(..., ge=1),
    admin: CurrentUser = Depends(get_current_admin),
    db: AsyncSession = Depends(get_master_db),
):
    await AdminService.unblind_post(post_id, db=db)
    return api_response(request, code=ApiCode.OK, data=UnblindedResponse())


@router.patch(
    "/posts/{post_id}/reset-reports",
    status_code=200,
    response_model=ApiResponse[ResetReportsResponse],
)
async def reset_post_reports(
    request: Request,
    post_id: int = Path(..., ge=1),
    admin: CurrentUser = Depends(get_current_admin),
    db: AsyncSession = Depends(get_master_db),
):
    await AdminService.reset_post_reports(post_id, db=db)
    return api_response(request, code=ApiCode.OK, data=ResetReportsResponse())


@router.patch(
    "/users/{user_id}/suspend",
    status_code=200,
    response_model=ApiResponse[SuspendedResponse],
)
async def suspend_user(
    request: Request,
    user_id: int = Path(..., ge=1),
    admin: CurrentUser = Depends(get_current_admin),
    db: AsyncSession = Depends(get_master_db),
):
    await AdminService.suspend_user(user_id, db=db)
    return api_response(request, code=ApiCode.OK, data=SuspendedResponse())


@router.patch(
    "/users/{user_id}/activate",
    status_code=200,
    response_model=ApiResponse[ActivatedResponse],
)
async def activate_user(
    request: Request,
    user_id: int = Path(..., ge=1),
    admin: CurrentUser = Depends(get_current_admin),
    db: AsyncSession = Depends(get_master_db),
):
    await AdminService.activate_user(user_id, db=db)
    return api_response(request, code=ApiCode.OK, data=ActivatedResponse())


@router.patch(
    "/posts/{post_id}/blind",
    status_code=200,
    response_model=ApiResponse[BlindedResponse],
)
async def blind_post(
    request: Request,
    post_id: int = Path(..., ge=1),
    admin: CurrentUser = Depends(get_current_admin),
    db: AsyncSession = Depends(get_master_db),
):
    await AdminService.blind_post(post_id, db=db)
    return api_response(request, code=ApiCode.OK, data=BlindedResponse())


@router.delete(
    "/posts/{post_id}",
    status_code=200,
    response_model=ApiResponse[None],
)
async def delete_post_admin(
    request: Request,
    post_id: int = Path(..., ge=1),
    admin: CurrentUser = Depends(get_current_admin),
    db: AsyncSession = Depends(get_master_db),
):
    await AdminService.delete_post(post_id, db=db)
    return api_response(request, code=ApiCode.POST_DELETED, data=None)


@router.patch(
    "/comments/{comment_id}/unblind",
    status_code=200,
    response_model=ApiResponse[UnblindedResponse],
)
async def unblind_comment(
    request: Request,
    comment_id: int = Path(..., ge=1),
    admin: CurrentUser = Depends(get_current_admin),
    db: AsyncSession = Depends(get_master_db),
):
    await AdminService.unblind_comment(comment_id, db=db)
    return api_response(request, code=ApiCode.OK, data=UnblindedResponse())


@router.patch(
    "/comments/{comment_id}/blind",
    status_code=200,
    response_model=ApiResponse[BlindedResponse],
)
async def blind_comment(
    request: Request,
    comment_id: int = Path(..., ge=1),
    admin: CurrentUser = Depends(get_current_admin),
    db: AsyncSession = Depends(get_master_db),
):
    await AdminService.blind_comment(comment_id, db=db)
    return api_response(request, code=ApiCode.OK, data=BlindedResponse())


@router.patch(
    "/comments/{comment_id}/reset-reports",
    status_code=200,
    response_model=ApiResponse[ResetReportsResponse],
)
async def reset_comment_reports(
    request: Request,
    comment_id: int = Path(..., ge=1),
    admin: CurrentUser = Depends(get_current_admin),
    db: AsyncSession = Depends(get_master_db),
):
    await AdminService.reset_comment_reports(comment_id, db=db)
    return api_response(request, code=ApiCode.OK, data=ResetReportsResponse())


@router.delete(
    "/posts/{post_id}/comments/{comment_id}",
    status_code=200,
    response_model=ApiResponse[None],
)
async def delete_comment_admin(
    request: Request,
    post_id: int = Path(..., ge=1),
    comment_id: int = Path(..., ge=1),
    admin: CurrentUser = Depends(get_current_admin),
    db: AsyncSession = Depends(get_master_db),
):
    await AdminService.delete_comment(post_id, comment_id, db=db)
    return api_response(request, code=ApiCode.OK, data=None)
