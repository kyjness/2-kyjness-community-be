# 관리자 전용 API. 모든 엔드포인트 Depends(get_current_admin).
import logging
from typing import Any

from fastapi import APIRouter, BackgroundTasks, Depends, Path, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.admin.schema import (
    ActivatedResponse,
    BlindedResponse,
    MediaSweepResponse,
    ReportedPostItem,
    ResetReportsResponse,
    SuspendedResponse,
    UnblindedResponse,
)
from app.admin.service import AdminService
from app.api.dependencies import CurrentUser, get_current_admin, get_master_db
from app.common import ApiCode, ApiResponse, PaginatedResponse, api_response
from app.db import AsyncSessionLocal
from app.media.service import MediaService

router = APIRouter(prefix="/admin", tags=["admin"])
log = logging.getLogger(__name__)


@router.post(
    "/media/sweep",
    status_code=202,
    response_model=ApiResponse[MediaSweepResponse],
)
async def sweep_unused_media(
    request: Request,
    background_tasks: BackgroundTasks,
    _admin: CurrentUser = Depends(get_current_admin),
):
    async def _sweep_task(session_maker: Any) -> None:
        # BackgroundTasks는 응답 후 실행되므로, request-scoped db 세션이 아니라 독립 커넥션을 열어야 합니다.
        try:
            async with session_maker() as bg_db:
                deleted_count = await MediaService.sweep_unused_images(db=bg_db)
                if deleted_count:
                    log.info("media_sweep_done deleted_count=%s", deleted_count)
                else:
                    log.info("media_sweep_done deleted_count=0")
        except Exception:
            # 백그라운드 실패는 클라이언트에 재전달하지 않음(202는 '시작'만 보장).
            log.warning("media_sweep_failed", exc_info=True)

    background_tasks.add_task(_sweep_task, AsyncSessionLocal)
    return api_response(
        request,
        code=ApiCode.OK,
        data=MediaSweepResponse(),
        message="백그라운드에서 정리가 시작되었습니다.",
    )


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
    post_id: str = Path(..., min_length=26, max_length=26),
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
    post_id: str = Path(..., min_length=26, max_length=26),
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
    user_id: str = Path(..., min_length=26, max_length=26),
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
    user_id: str = Path(..., min_length=26, max_length=26),
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
    post_id: str = Path(..., min_length=26, max_length=26),
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
    post_id: str = Path(..., min_length=26, max_length=26),
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
    comment_id: str = Path(..., min_length=26, max_length=26),
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
    comment_id: str = Path(..., min_length=26, max_length=26),
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
    comment_id: str = Path(..., min_length=26, max_length=26),
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
    post_id: str = Path(..., min_length=26, max_length=26),
    comment_id: str = Path(..., min_length=26, max_length=26),
    admin: CurrentUser = Depends(get_current_admin),
    db: AsyncSession = Depends(get_master_db),
):
    await AdminService.delete_comment(post_id, comment_id, db=db)
    return api_response(request, code=ApiCode.OK, data=None)
