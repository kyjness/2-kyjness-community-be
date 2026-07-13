# 알림 Celery 태스크(동기 시그니처 → async_bridge).

import logging

from app.core.celery import celery_app
from app.worker.async_bridge import run_async_task
from app.worker.jobs.notification_delivery import (
    NotificationDeliverySkip,
    deliver_notification_sns_async,
)

log = logging.getLogger(__name__)


@celery_app.task(
    bind=True,
    name="app.worker.tasks.notifications.deliver_notification_sns",
    max_retries=3,
    default_retry_delay=60,
    retry_backoff=True,
    retry_jitter=True,
    queue="high_priority",
    soft_time_limit=120,
    time_limit=180,
)
def deliver_notification_sns(
    self,
    *,
    notification_id: str,
    user_id: str,
    idempotency_key: str,
) -> dict[str, str]:
    """알림 오프라인 배송(SNS publish). 외부 I/O라 재시도·백오프가 필요해 워커로 오프로드.

    멱등 마킹은 publish 성공 후에만 수행되어 재시도가 유실되지 않는다(잡 참조).
    """
    try:
        return run_async_task(
            deliver_notification_sns_async(
                notification_id=notification_id,
                user_id=user_id,
                idempotency_key=idempotency_key,
            )
        )
    except NotificationDeliverySkip as e:
        log.warning("deliver_notification_sns_skip: %s", e)
        return {"status": "skipped", "reason": str(e)}
    except Exception as exc:
        log.exception("deliver_notification_sns_failed notification_id=%s", notification_id)
        raise self.retry(exc=exc) from exc
