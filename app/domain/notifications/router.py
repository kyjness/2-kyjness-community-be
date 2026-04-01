# 알림 REST + SSE. 목록/읽음은 ApiResponse, 스트림은 text/event-stream.
from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import JSONResponse, StreamingResponse
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import (
    CurrentUser,
    get_current_user,
    get_master_db,
    get_optional_redis,
    get_slave_db,
)
from app.common import ApiCode, ApiResponse, PaginatedResponse, api_response, dump_api_response
from app.notifications.schema import (
    MarkNotificationsReadData,
    MarkNotificationsReadRequest,
    NotificationItem,
)
from app.notifications.service import NotificationService

router = APIRouter(prefix="/notifications", tags=["notifications"])


@router.get(
    "/stream",
    status_code=200,
    summary="실시간 알림(SSE)",
    response_class=StreamingResponse,
)
async def notifications_stream(
    request: Request,
    user: CurrentUser = Depends(get_current_user),
    redis: Redis | None = Depends(get_optional_redis),
):
    """Redis Pub/Sub를 구독하는 SSE. 앱에 Redis가 없으면 503(JSON)."""

    if redis is None:
        return JSONResponse(
            status_code=503,
            content=dump_api_response(
                request,
                code=ApiCode.NOTIFICATION_SSE_UNAVAILABLE,
                message="실시간 알림 스트림을 사용할 수 없습니다. Redis 연결 후 재시도하거나 목록 API를 사용하세요.",
                data=None,
            ),
        )
    return StreamingResponse(
        NotificationService.sse_subscribe(redis, user.id),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("", status_code=200, response_model=ApiResponse[PaginatedResponse[NotificationItem]])
async def list_notifications(
    request: Request,
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_slave_db),
):
    data = await NotificationService.list_notifications(user.id, page=page, size=size, db=db)
    return api_response(request, code=ApiCode.OK, data=data)


@router.patch("/read", status_code=200, response_model=ApiResponse[MarkNotificationsReadData])
async def mark_notifications_read(
    request: Request,
    body: MarkNotificationsReadRequest,
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_master_db),
):
    ids = body.ids if body.ids else None
    n = await NotificationService.mark_read(user.id, ids=ids, db=db)
    return api_response(
        request,
        code=ApiCode.OK,
        data=MarkNotificationsReadData(updated_count=n),
    )
