# 알림 SNS 배송 Job: DB 행 검증 → SNS publish → 성공 후 멱등 마킹. Celery 태스크는 tasks/ 에서 호출.

import asyncio
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
from app.db import get_connection
from app.domain.notifications.model import Notification
from app.domain.notifications.service import NotificationService

log = logging.getLogger(__name__)

_IDEMP_KEY_PREFIX = "celery:notif:delivered:"

# 워커 프로세스당 SNS 클라이언트 1개 재사용(publish마다 생성하면 커넥션·시그너 비용 반복).
_sns_client: Any = None


class NotificationDeliverySkip(Exception):
    """재시도 불필요(미존재·멱등 스킵·SNS 비활성)."""


def _get_sns_client() -> Any:
    global _sns_client
    if _sns_client is None:
        import boto3

        _sns_client = boto3.client("sns", region_name=settings.AWS_REGION or "ap-northeast-2")
    return _sns_client


def _sns_publish_sync(topic_arn: str, message_json: str) -> None:
    _get_sns_client().publish(TopicArn=topic_arn, Message=message_json)


async def _already_delivered(redis: Redis | None, key: str) -> bool:
    if redis is None:
        return False
    r = cast(Any, redis)
    return bool(await r.get(f"{_IDEMP_KEY_PREFIX}{key}"))


async def _mark_delivered(redis: Redis | None, key: str, ttl_seconds: int) -> None:
    """publish 성공 후에만 마킹 — 실패 재시도가 멱등 skip으로 유실되지 않게 한다."""
    if redis is None:
        return
    r = cast(Any, redis)
    try:
        await r.set(f"{_IDEMP_KEY_PREFIX}{key}", "1", ex=ttl_seconds)
    except Exception as e:
        # 마킹 실패 시 재시도가 재publish할 수 있으나(at-least-once) SNS 구독자가 흡수한다.
        log.warning("notification_delivery_idemp_mark_failed key=%s err=%s", key, e)


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


async def deliver_notification_sns_async(
    *,
    notification_id: str,
    user_id: str,
    idempotency_key: str,
) -> dict[str, str]:
    """알림 행을 DB에서 재검증 후 SNS로 발행한다(오프라인 푸시·다운스트림 구독).

    페이로드는 태스크 인자가 아니라 DB 행에서 구성한다 — 재시도 시점에도 진실은 DB.
    멱등 검사(GET)→publish→마킹(SET) 순서라 경쟁 중복 publish가 가능하지만(at-least-once),
    실패 재시도 유실보다 중복이 낫다는 선택이다.
    """
    if not settings.SNS_TOPIC_ARN:
        raise NotificationDeliverySkip("sns topic not configured")
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
        if await _already_delivered(redis, idempotency_key):
            log.info("notification_delivery_skip_idempotent key=%s", idempotency_key)
            return {"status": "skipped", "reason": "idempotent"}

        async with get_connection() as db:
            async with db.begin():
                row = await _load_notification(db, notification_id=nid, user_id=uid)

        payload = NotificationService.build_sns_payload(
            recipient_user_id=uid,
            notification_id=row.id,
            kind=NotificationKind(row.kind),
            actor_id=row.actor_id,
            post_id=row.post_id,
            comment_id=row.comment_id,
        )
        await asyncio.to_thread(
            _sns_publish_sync, settings.SNS_TOPIC_ARN, json.dumps(payload, ensure_ascii=False)
        )
        await _mark_delivered(redis, idempotency_key, settings.CELERY_TASK_IDEMPOTENCY_TTL_SECONDS)
        log.info("notification_sns_delivered notification_id=%s user_id=%s", nid, uid)
        return {"status": "delivered", "notification_id": str(nid)}
    finally:
        if redis is not None:
            await redis.aclose()
