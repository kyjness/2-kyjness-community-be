# 알림 오프로딩 Job: DB 조회·멱등·Redis Pub/Sub(SSE) 재전달. Celery 태스크는 tasks/ 에서 호출.

import json
import logging
from typing import Any, cast
from uuid import UUID

from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.enums import NotificationKind
from app.core.config import settings
from app.core.ids import parse_public_id_value
from app.db import AsyncSessionLocal, get_connection
from app.domain.notifications.model import Notification
from app.domain.notifications.service import NotificationService, notification_channel_for_user

log = logging.getLogger(__name__)

_IDEMP_KEY_PREFIX = "celery:notif:delivered:"


class NotificationDeliverySkip(Exception):
    """재시도 불필요(미존재·멱등 스킵)."""


async def _acquire_idempotency(redis: Redis | None, key: str, ttl_seconds: int) -> bool:
    if redis is None:
        return True
    r = cast(Any, redis)
    full_key = f"{_IDEMP_KEY_PREFIX}{key}"
    return bool(await r.set(full_key, "1", nx=True, ex=ttl_seconds))


async def _load_notification(
    db: AsyncSession,
    *,
    notification_id: UUID,
    user_id: UUID,
) -> Notification:
    row = (
        await db.execute(
            select(Notification).where(
                Notification.id == notification_id,
                Notification.user_id == user_id,
            )
        )
    ).scalar_one_or_none()
    if row is None:
        raise NotificationDeliverySkip("notification not found")
    return row


async def deliver_notification_async(
    *,
    notification_id: str,
    user_id: str,
    idempotency_key: str,
) -> dict[str, str]:
    """알림 행 검증 후 Redis Pub/Sub로 실시간 전달(푸시/SSE 파이프라인 대체·보조)."""
    nid = parse_public_id_value(notification_id)
    uid = parse_public_id_value(user_id)
    redis: Redis | None = None
    if settings.REDIS_URL:
        redis = cast(Any, Redis).from_url(
            settings.REDIS_URL,
            decode_responses=True,
            max_connections=4,
        )
    try:
        if not await _acquire_idempotency(
            redis, idempotency_key, settings.CELERY_TASK_IDEMPOTENCY_TTL_SECONDS
        ):
            log.info("notification_delivery_skip_idempotent key=%s", idempotency_key)
            return {"status": "skipped", "reason": "idempotent"}

        async with get_connection() as db:
            async with db.begin():
                row = await _load_notification(db, notification_id=nid, user_id=uid)

        kind = NotificationKind(row.kind)
        if redis is not None:
            payload = NotificationService.build_realtime_payload(
                row.id,
                kind,
                actor_id=row.actor_id,
                post_id=row.post_id,
                comment_id=row.comment_id,
            )
            r = cast(Any, redis)
            await r.publish(
                notification_channel_for_user(uid),
                json.dumps(payload, ensure_ascii=False),
            )

        log.info("notification_delivery_done notification_id=%s user_id=%s", nid, uid)
        return {"status": "delivered", "notification_id": str(nid)}
    finally:
        if redis is not None:
            await redis.aclose()


async def mark_notifications_read_async(
    *,
    user_id: str,
    notification_ids: list[str] | None,
) -> int:
    """읽음 처리 Job 샘플(UoW 단일 트랜잭션)."""
    uid = parse_public_id_value(user_id)
    ids = [parse_public_id_value(i) for i in (notification_ids or [])]
    async with AsyncSessionLocal() as db:
        async with db.begin():
            from app.domain.notifications.model import NotificationsModel

            return await NotificationsModel.mark_read(uid, notification_ids=ids or None, db=db)
