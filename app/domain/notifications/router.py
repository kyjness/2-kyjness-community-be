# 알림 REST + SSE. 목록/읽음은 ApiResponse, 스트림은 text/event-stream.
from __future__ import annotations

from typing import Annotated, cast

from celery import Task
from fastapi import APIRouter, Depends, Header, Path, Query, Request
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
from app.common import (
    ApiCode,
    ApiResponse,
    CursorPage,
    OptionalPublicId,
    PublicId,
    api_response,
    dump_api_response,
)
from app.common.exceptions import InvalidRequestException
from app.core.config import settings
from app.core.ids import uuid_to_base62
from app.domain.notifications.schema import (
    DispatchNotificationTaskData,
    MarkNotificationsReadData,
    MarkNotificationsReadRequest,
    NotificationItem,
)
from app.domain.notifications.service import NotificationService

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


@router.get("", status_code=200, response_model=ApiResponse[CursorPage[NotificationItem]])
async def list_notifications(
    request: Request,
    cursor: Annotated[
        OptionalPublicId,
        Query(description="무한 스크롤: 직전 응답의 마지막 알림 id(공개 ID). 미지정 시 처음부터."),
    ] = None,
    size: int = Query(20, ge=1, le=100),
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_slave_db),
):
    items, has_more = await NotificationService.list_notifications(
        user.id, cursor_id=cursor, size=size, db=db
    )
    return api_response(request, code=ApiCode.OK, data=CursorPage(items=items, has_more=has_more))


@router.post(
    "/{notification_id}/dispatch",
    status_code=202,
    response_model=ApiResponse[DispatchNotificationTaskData],
)
async def dispatch_notification_delivery(
    request: Request,
    notification_id: Annotated[PublicId, Path(..., description="알림 공개 ID (Base62)")],
    user: CurrentUser = Depends(get_current_user),
    x_idempotency_key: str | None = Header(default=None, alias="X-Idempotency-Key"),
):
    """알림 푸시/SSE 재전달을 Celery high_priority 큐로 오프로딩."""
    if not settings.CELERY_ENABLED:
        raise InvalidRequestException(
            message="Celery worker is disabled. Set CELERY_ENABLED=true and run the worker."
        )
    idem = (x_idempotency_key or "").strip() or f"dispatch:{uuid_to_base62(notification_id)}"
    from app.worker.tasks.notifications import deliver_notification_push

    task = cast(Task, deliver_notification_push)
    async_result = task.delay(
        notification_id=uuid_to_base62(notification_id),
        user_id=uuid_to_base62(user.id),
        idempotency_key=idem,
    )
    return api_response(
        request,
        code=ApiCode.OK,
        data=DispatchNotificationTaskData(task_id=async_result.id, queue="high_priority"),
        message="알림 전달 작업이 큐에 등록되었습니다.",
    )


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
