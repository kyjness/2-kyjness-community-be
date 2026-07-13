# 알림 애플리케이션 서비스: PostgreSQL 영속화, 커밋 이후 Redis Pub/Sub, SSE 구독 스트림.

import asyncio
import json
import logging
from collections.abc import AsyncIterator
from typing import Any, cast
from uuid import UUID

from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.enums import NotificationKind
from app.core.config import settings
from app.core.ids import uuid_to_base62
from app.domain.notifications.model import Notification, NotificationsModel
from app.domain.notifications.schema import NotificationItem

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

    @staticmethod
    def _sns_summary_for_kind(kind: NotificationKind) -> str:
        if kind == NotificationKind.COMMENT_ON_POST:
            return "회원님의 게시글에 댓글이 달렸습니다."
        if kind == NotificationKind.LIKE_POST:
            return "회원님의 게시글에 좋아요가 눌렸습니다."
        if kind == NotificationKind.LIKE_COMMENT:
            return "회원님의 댓글에 좋아요가 눌렸습니다."
        return kind.value

    @staticmethod
    def build_sns_payload(
        *,
        recipient_user_id: UUID,
        notification_id: UUID,
        kind: NotificationKind,
        actor_id: UUID | None,
        post_id: UUID | None,
        comment_id: UUID | None,
    ) -> dict[str, Any]:
        """SNS `Message`에 실을 JSON 직렬화용 페이로드(구독자·Lambda에서 파싱)."""

        base = NotificationService.build_realtime_payload(
            notification_id,
            kind,
            actor_id=actor_id,
            post_id=post_id,
            comment_id=comment_id,
        )
        return {
            **base,
            "recipientUserId": uuid_to_base62(recipient_user_id),
            "message": NotificationService._sns_summary_for_kind(kind),
        }

    @staticmethod
    def _sns_publish_sync(topic_arn: str, message_json: str, region: str) -> None:
        import boto3

        client = boto3.client("sns", region_name=region)
        client.publish(TopicArn=topic_arn, Message=message_json)

    @classmethod
    async def _dispatch_sns_publish(
        cls,
        *,
        recipient_user_id: UUID,
        notification_id: UUID,
        kind: NotificationKind,
        actor_id: UUID | None,
        post_id: UUID | None,
        comment_id: UUID | None,
    ) -> None:
        """오프라인 배송(SNS)은 재시도·백오프가 필요한 외부 I/O라 Celery로 오프로드한다.

        워커 비활성(CELERY_ENABLED=false)·브로커 장애 시에는 인라인 fire-and-forget으로
        폴백한다(fail-open — 실시간 인앱 경로와 DB는 이미 확보된 상태).
        """
        if not settings.SNS_TOPIC_ARN:
            return
        if settings.CELERY_ENABLED:
            try:
                from app.worker.tasks.notifications import deliver_notification_sns

                # 결정적 멱등키: 같은 알림의 중복 enqueue가 워커에서 1회 배송으로 수렴.
                await asyncio.to_thread(
                    cast(Any, deliver_notification_sns).delay,
                    notification_id=uuid_to_base62(notification_id),
                    user_id=uuid_to_base62(recipient_user_id),
                    idempotency_key=f"sns:{uuid_to_base62(notification_id)}",
                )
                return
            except Exception:
                log.exception(
                    "알림 SNS Celery enqueue 실패 — 인라인 폴백. notification_id=%s",
                    notification_id,
                )
        cls._schedule_sns_publish(
            recipient_user_id=recipient_user_id,
            notification_id=notification_id,
            kind=kind,
            actor_id=actor_id,
            post_id=post_id,
            comment_id=comment_id,
        )

    @classmethod
    def _schedule_sns_publish(
        cls,
        *,
        recipient_user_id: UUID,
        notification_id: UUID,
        kind: NotificationKind,
        actor_id: UUID | None,
        post_id: UUID | None,
        comment_id: UUID | None,
    ) -> None:
        if not settings.SNS_TOPIC_ARN:
            return
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            return

        async def _run() -> None:
            await cls._publish_sns_task(
                recipient_user_id=recipient_user_id,
                notification_id=notification_id,
                kind=kind,
                actor_id=actor_id,
                post_id=post_id,
                comment_id=comment_id,
            )

        loop.create_task(_run())

    @classmethod
    async def _publish_sns_task(
        cls,
        *,
        recipient_user_id: UUID,
        notification_id: UUID,
        kind: NotificationKind,
        actor_id: UUID | None,
        post_id: UUID | None,
        comment_id: UUID | None,
    ) -> None:
        topic = settings.SNS_TOPIC_ARN
        region = settings.AWS_REGION or "ap-northeast-2"
        payload = cls.build_sns_payload(
            recipient_user_id=recipient_user_id,
            notification_id=notification_id,
            kind=kind,
            actor_id=actor_id,
            post_id=post_id,
            comment_id=comment_id,
        )
        message_json = json.dumps(payload, ensure_ascii=False)
        try:
            await asyncio.to_thread(cls._sns_publish_sync, topic, message_json, region)
        except Exception:
            log.exception(
                "알림 SNS publish 실패(인앱·DB는 유지). recipient=%s topic=%s",
                recipient_user_id,
                topic,
            )

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

        if redis is not None:
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

        await cls._dispatch_sns_publish(
            recipient_user_id=recipient_user_id,
            notification_id=notification_id,
            kind=kind,
            actor_id=actor_id,
            post_id=post_id,
            comment_id=comment_id,
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
        cursor_id: UUID | None,
        size: int,
        db: AsyncSession,
    ) -> tuple[list[NotificationItem], bool]:
        async with db.begin():
            rows, has_more = await NotificationsModel.list_for_user(
                user_id, cursor_id=cursor_id, size=size, db=db
            )
        return [cls.row_to_item(r) for r in rows], has_more

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
