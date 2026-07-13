# 유저 대상 실시간 팬아웃 공용 인프라: 단일 채널 + envelope(수신자 UUID) 발행,
# 인스턴스당 전용 Pub/Sub 연결 1개로 여러 채널을 구독해 로컬 핸들러로 디스패치.
#
# 연결마다 공유 풀에서 pubsub을 점유하면 동시 구독자 수가 풀 한도를 잠식해
# rate limit·인증 캐시·조회수 버퍼가 연쇄 fail-open된다 — 구독 소켓은 프로세스당
# 1개로 고정하고, 수신자별 분기는 로컬 매니저(chat WS·알림 SSE)가 맡는다.

import asyncio
import json
import logging
from collections.abc import Awaitable, Callable
from typing import Any, cast
from uuid import UUID

from redis.asyncio import Redis

log = logging.getLogger(__name__)

_MESSAGE_POLL_TIMEOUT_SEC = 1.0

# (target_user_id, payload) → 로컬 전달. payload는 클라이언트에 그대로 보낼 텍스트.
UserEnvelopeHandler = Callable[[UUID, str], Awaitable[None]]


async def publish_user_envelope(
    redis: Redis | None,
    channel: str,
    *,
    target_user_id: UUID,
    payload: str,
) -> bool:
    """envelope PUBLISH. 성공 여부를 반환한다 — False면 호출부가 로컬 전달로 폴백해야
    같은 인스턴스의 수신자라도 유실되지 않는다(예외를 여기서 삼키므로 반환값이 유일한 신호)."""
    if redis is None or not payload:
        return False
    env = json.dumps(
        {"target_user_id": str(target_user_id), "payload": payload},
        ensure_ascii=False,
    )
    try:
        r = cast(Any, redis)
        await r.publish(channel, env)
        return True
    except Exception:
        log.exception("pubsub publish 실패 channel=%s", channel)
        return False


def parse_user_envelope(raw: str) -> tuple[UUID, str] | None:
    try:
        data = json.loads(raw)
        uid = UUID(str(data["target_user_id"]))
        payload = data["payload"]
        if not isinstance(payload, str):
            payload = json.dumps(payload, ensure_ascii=False)
        return uid, payload
    except Exception:
        log.warning("pubsub envelope invalid", exc_info=False)
        return None


async def run_user_fanout_listener(
    *,
    redis_url: str,
    handlers: dict[str, UserEnvelopeHandler],
    stop_event: asyncio.Event,
) -> None:
    """백그라운드: 전용 Redis 연결 1개로 `handlers`의 모든 채널을 구독하고,
    수신 envelope를 채널별 핸들러로 로컬 팬아웃한다."""
    if not redis_url or not handlers:
        return
    client: Any = None
    pubsub: Any = None
    try:
        # redis.asyncio 타입 스텁에 from_url 미정의 → 런타임 팩토리만 사용.
        client = cast(Any, Redis).from_url(redis_url, decode_responses=True)
        await client.ping()
        pubsub = client.pubsub()
        await pubsub.subscribe(*handlers)
        log.info("user fanout pubsub subscribed channels=%s", sorted(handlers))
        while not stop_event.is_set():
            try:
                msg = await pubsub.get_message(
                    ignore_subscribe_messages=True,
                    timeout=_MESSAGE_POLL_TIMEOUT_SEC,
                )
            except asyncio.CancelledError:
                raise
            except Exception:
                log.exception("pubsub get_message 실패, 잠시 대기 후 재시도")
                await asyncio.sleep(0.5)
                continue
            if msg is None:
                continue
            if msg.get("type") != "message":
                continue
            channel = msg.get("channel")
            if isinstance(channel, bytes):
                channel = channel.decode("utf-8")
            handler = handlers.get(channel) if isinstance(channel, str) else None
            if handler is None:
                continue
            raw = msg.get("data")
            if isinstance(raw, bytes):
                raw = raw.decode("utf-8")
            if not isinstance(raw, str) or not raw:
                continue
            parsed = parse_user_envelope(raw)
            if parsed is None:
                continue
            target_user_id, payload = parsed
            try:
                await handler(target_user_id, payload)
            except Exception:
                log.exception("local fanout 실패 channel=%s user=%s", channel, target_user_id)
    except asyncio.CancelledError:
        raise
    except Exception:
        log.exception("pubsub listener 종료 예외")
    finally:
        if pubsub is not None:
            try:
                await pubsub.unsubscribe(*handlers)
            except Exception:
                log.exception("pubsub unsubscribe 실패")
            try:
                await pubsub.aclose()
            except Exception:
                log.exception("pubsub aclose 실패")
        if client is not None:
            try:
                await client.aclose()
            except Exception:
                log.exception("pubsub redis aclose 실패")
