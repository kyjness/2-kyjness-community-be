# 알림 애플리케이션 서비스: PostgreSQL 영속화, 커밋 이후 Redis Pub/Sub, SSE 구독 스트림.
from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import AsyncIterator
from typing import Any, cast
from uuid import UUID

from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.enums import NotificationKind
from app.common.schemas import PaginatedResponse
from app.core.ids import uuid_to_base62
from app.notifications.model import Notification, NotificationsModel
from app.notifications.schema import NotificationItem

log = logging.getLogger(__name__)

_NOTIF_USER_CHANNEL_PREFIX = "notif:user:"


def notification_channel_for_user(user_id: UUID) -> str:
    """Redis Pub/Sub 채널명. UUID 문자열로 정규화."""

    return f"{_NOTIF_USER_CHANNEL_PREFIX}{user_id}"


class NotificationService:
    """수신자별 알림 레코드와 실시간 전달을 조율. Publish는 항상 트랜잭션 커밋 이후 호출."""

    @staticmethod
    def build_realtime_payload(
        notification_id: UUID,
        kind: NotificationKind,
        *,
        actor_id: UUID | None,
        post_id: UUID | None,
        comment_id: UUID | None,
    ) -> dict[str, Any]:
        """SSE `data:` JSON. 필드명은 프론트 camelCase 관례에 맞춤."""

        return {
            "notificationId": uuid_to_base62(notification_id),
            "kind": kind.value,
            "actorId": None if actor_id is None else uuid_to_base62(actor_id),
            "postId": None if post_id is None else uuid_to_base62(post_id),
            "commentId": None if comment_id is None else uuid_to_base62(comment_id),
        }

    @classmethod
    async def publish_after_commit(
        cls,
        redis: Redis | None,
        *,
        recipient_user_id: UUID,
        notification_id: UUID,
        kind: NotificationKind,
        actor_id: UUID | None,
        post_id: UUID | None,
        comment_id: UUID | None,
    ) -> None:
        """트랜잭션이 성공적으로 커밋된 뒤에만 호출. Redis 장애 시 DB 데이터는 유지(fail-open)."""

        if redis is None:
            return
        payload = cls.build_realtime_payload(
            notification_id,
            kind,
            actor_id=actor_id,
            post_id=post_id,
            comment_id=comment_id,
        )
        try:
            r = cast(Any, redis)
            await r.publish(
                notification_channel_for_user(recipient_user_id),
                json.dumps(payload, ensure_ascii=False),
            )
        except Exception:
            log.exception(
                "알림 Redis publish 실패(수신자는 GET /notifications 로 동기화 가능). recipient=%s",
                recipient_user_id,
            )

    @staticmethod
    def row_to_item(row: Notification) -> NotificationItem:
        return NotificationItem(
            id=row.id,
            kind=NotificationKind(row.kind),
            actor_id=row.actor_id,
            post_id=row.post_id,
            comment_id=row.comment_id,
            read_at=row.read_at,
            created_at=row.created_at,
        )

    @classmethod
    async def list_notifications(
        cls,
        user_id: UUID,
        *,
        page: int,
        size: int,
        db: AsyncSession,
    ) -> PaginatedResponse[NotificationItem]:
        async with db.begin():
            rows, total = await NotificationsModel.list_for_user(
                user_id, page=page, size=size, db=db
            )
        if not rows:
            return PaginatedResponse(items=[], has_more=False, total=total)
        has_more = page * size < total
        return PaginatedResponse(
            items=[cls.row_to_item(r) for r in rows],
            has_more=has_more,
            total=total,
        )

    @classmethod
    async def mark_read(
        cls,
        user_id: UUID,
        *,
        ids: list[UUID] | None,
        db: AsyncSession,
    ) -> int:
        async with db.begin():
            return await NotificationsModel.mark_read(user_id, notification_ids=ids, db=db)

    @classmethod
    async def purge_old_notifications(
        cls,
        *,
        older_than_days: int = 30,
        chunk_size: int = 2_000,
        db: AsyncSession,
    ) -> int:
        async with db.begin():
            return await NotificationsModel.purge_older_than_days(
                older_than_days=older_than_days,
                chunk_size=chunk_size,
                db=db,
            )

    @staticmethod
    async def sse_subscribe(
        redis: Redis,
        user_id: UUID,
        *,
        heartbeat_interval_sec: float = 25.0,
    ) -> AsyncIterator[str]:
        """로그인 유저 전용 채널 구독. 클라이언트 연결 해제 시 제너레이터 취소 → pubsub teardown."""

        channel = notification_channel_for_user(user_id)
        r = cast(Any, redis)
        pubsub = r.pubsub()
        await pubsub.subscribe(channel)
        try:
            while True:
                message = await pubsub.get_message(
                    ignore_subscribe_messages=True,
                    timeout=heartbeat_interval_sec,
                )
                if message is None:
                    yield ": ping\n\n"
                    continue
                if message.get("type") != "message":
                    continue
                raw = message.get("data")
                if isinstance(raw, bytes):
                    raw = raw.decode("utf-8")
                yield f"data: {raw}\n\n"
        except asyncio.CancelledError:
            raise
        finally:
            try:
                await pubsub.unsubscribe(channel)
            except Exception:
                log.exception("알림 pubsub unsubscribe 실패(user_id=%s)", user_id)
            try:
                await pubsub.aclose()
            except Exception:
                log.exception("알림 pubsub aclose 실패(user_id=%s)", user_id)
