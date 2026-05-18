# 알림 Celery 태스크(동기 시그니처 → async_bridge).
from __future__ import annotations

import logging

from celery.exceptions import Retry

from app.core.celery import celery_app
from app.worker.async_bridge import run_async_task
from app.worker.jobs.notification_delivery import (
    NotificationDeliverySkip,
    deliver_notification_async,
    mark_notifications_read_async,
)

log = logging.getLogger(__name__)


@celery_app.task(
    bind=True,
    name="app.worker.tasks.notifications.deliver_notification_push",
    max_retries=3,
    default_retry_delay=60,
    retry_backoff=True,
    retry_jitter=True,
    queue="high_priority",
    soft_time_limit=120,
    time_limit=180,
)
def deliver_notification_push(
    self,
    *,
    notification_id: str,
    user_id: str,
    idempotency_key: str,
) -> dict[str, str]:
    """DB 알림 검증 후 Redis Pub/Sub 전달. idempotency_key로 재시도 중복 방지."""
    try:
        return run_async_task(
            deliver_notification_async(
                notification_id=notification_id,
                user_id=user_id,
                idempotency_key=idempotency_key,
            )
        )
    except NotificationDeliverySkip as e:
        log.warning("deliver_notification_push_skip: %s", e)
        return {"status": "skipped", "reason": str(e)}
    except Exception as exc:
        log.exception("deliver_notification_push_failed notification_id=%s", notification_id)
        raise self.retry(exc=exc) from exc


@celery_app.task(
    bind=True,
    name="app.worker.tasks.notifications.mark_notifications_read_job",
    max_retries=2,
    default_retry_delay=30,
    queue="default",
)
def mark_notifications_read_job(
    self,
    *,
    user_id: str,
    notification_ids: list[str] | None = None,
) -> dict[str, int]:
    try:
        count = run_async_task(
            mark_notifications_read_async(
                user_id=user_id,
                notification_ids=notification_ids,
            )
        )
        return {"updated_count": count}
    except Exception as exc:
        raise Retry(exc=exc) from exc
