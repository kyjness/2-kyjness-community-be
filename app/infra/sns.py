# SNS publish 공용 헬퍼 + 배송 멱등 스토어.
# 서비스 인라인 폴백과 Celery 워커 잡이 같은 클라이언트 캐시·같은 멱등 키를 공유해,
# 브로커 ack 유실 후 인라인 폴백 → 워커 재실행 같은 교차 경로에서도 이중 배송 창이 닫힌다.

import asyncio
import logging
from typing import Any, cast

from app.core.config import settings
from app.infra.redis import RedisLike

log = logging.getLogger(__name__)

DELIVERED_KEY_PREFIX = "celery:notif:delivered:"

# 프로세스당 SNS 클라이언트 1개 재사용(publish마다 생성하면 커넥션·시그너 비용 반복).
_sns_client: Any = None


def _get_sns_client() -> Any:
    global _sns_client
    if _sns_client is None:
        import boto3

        _sns_client = boto3.client("sns", region_name=settings.AWS_REGION or "ap-northeast-2")
    return _sns_client


def _publish_sync(topic_arn: str, message_json: str) -> None:
    _get_sns_client().publish(TopicArn=topic_arn, Message=message_json)


async def publish_sns(topic_arn: str, message_json: str) -> None:
    """동기 boto3 publish를 스레드로 — 이벤트 루프를 막지 않는다."""
    await asyncio.to_thread(_publish_sync, topic_arn, message_json)


async def already_delivered(redis: RedisLike | None, key: str) -> bool:
    """멱등 검사. Redis 부재·오류는 fail-open(미배송 취급) — 중복 publish는 구독자가 흡수."""
    if redis is None:
        return False
    try:
        return bool(await cast(Any, redis).get(f"{DELIVERED_KEY_PREFIX}{key}"))
    except Exception as e:
        log.warning("sns_delivered_check_failed key=%s err=%s", key, e)
        return False


async def mark_delivered(redis: RedisLike | None, key: str, ttl_seconds: int) -> None:
    """publish 성공 후에만 마킹 — 실패 재시도가 멱등 skip으로 유실되지 않게 한다."""
    if redis is None:
        return
    try:
        await cast(Any, redis).set(f"{DELIVERED_KEY_PREFIX}{key}", "1", ex=ttl_seconds)
    except Exception as e:
        # 마킹 실패 시 재시도가 재publish할 수 있으나(at-least-once) SNS 구독자가 흡수한다.
        log.warning("sns_delivered_mark_failed key=%s err=%s", key, e)


async def deliver_once(
    redis: RedisLike | None,
    idempotency_key: str,
    topic_arn: str,
    message_json: str,
    ttl_seconds: int,
) -> bool:
    """배송 안무의 단일 소스: 멱등 검사 → publish → **성공 후에만** 마킹.

    선마킹으로 바꾸면 publish 실패 건이 배송됨으로 기록돼 재시도가 멱등 skip으로
    유실된다 — 이 순서 불변식을 호출자(인라인 폴백·워커 잡)가 각자 재조립하지 않게
    여기에 고정한다. 반환: publish 수행 여부(False = 멱등 스킵)."""
    if await already_delivered(redis, idempotency_key):
        return False
    await publish_sns(topic_arn, message_json)
    await mark_delivered(redis, idempotency_key, ttl_seconds)
    return True
