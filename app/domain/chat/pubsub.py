# DM 채팅 분산 브로드캐스트: 단일 Pub/Sub 채널 + envelope에 수신자 UUID. 워커마다 구독 루프 1개.
from __future__ import annotations

import asyncio
import json
import logging
from typing import Any, cast
from uuid import UUID

from redis.asyncio import Redis

from app.domain.chat.manager import chat_connection_manager

log = logging.getLogger(__name__)

# 알림 notif:user:* 과 네임스페이스 분리. 클러스터 사용 시 단일 채널 패턴이면 동일 슬롯 이슈 없음.
CHAT_DM_FANOUT_CHANNEL = "puppytalk:channel:chat:dm"

_MESSAGE_POLL_TIMEOUT_SEC = 1.0


async def publish_message(redis: Redis | None, channel: str, message: str) -> None:
    """Redis PUBLISH. `redis`가 None이면 no-op(Fail-open)."""
    if redis is None or not message:
        return
    try:
        r = cast(Any, redis)
        await r.publish(channel, message)
    except Exception:
        log.exception("chat redis publish 실패 channel=%s", channel)


async def publish_chat_dm(
    redis: Redis | None,
    *,
    target_user_id: UUID,
    payload: str,
) -> None:
    """다른 워커/프로세스로 DM 페이로드 전달. `payload`는 클라이언트에 그대로 보낼 텍스트(보통 JSON 문자열)."""
    env = json.dumps(
        {"target_user_id": str(target_user_id), "payload": payload},
        ensure_ascii=False,
    )
    await publish_message(redis, CHAT_DM_FANOUT_CHANNEL, env)


def _parse_envelope(raw: str) -> tuple[UUID, str] | None:
    try:
        data = json.loads(raw)
        uid = UUID(str(data["target_user_id"]))
        payload = data["payload"]
        if not isinstance(payload, str):
            payload = json.dumps(payload, ensure_ascii=False)
        return uid, payload
    except Exception:
        log.warning("chat pubsub envelope invalid", exc_info=False)
        return None


async def subscribe_chat_channel(
    redis: Redis,
) -> Any:
    """테스트·확장용: PubSub 객체를 반환. 기본 운영 경로는 `run_chat_subscribe_listener`."""
    r = cast(Any, redis)
    pubsub = r.pubsub()
    await pubsub.subscribe(CHAT_DM_FANOUT_CHANNEL)
    return pubsub


async def run_chat_subscribe_listener(*, redis_url: str, stop_event: asyncio.Event) -> None:
    """백그라운드: 전용 Redis 연결로 채널 구독 → 로컬 `chat_connection_manager`로 푸시.

    풀에 묶인 `app.state.redis`와 분리해 Pub/Sub 전용 소켓을 쓴다(SSE 알림과 동일 패턴).
    """
    if not redis_url:
        return
    client: Any = None
    pubsub: Any = None
    try:
        # redis.asyncio 타입 스텁에 from_url 미정의 → 런타임 팩토리만 사용.
        client = cast(Any, Redis).from_url(redis_url, decode_responses=True)
        await client.ping()
        pubsub = client.pubsub()
        await pubsub.subscribe(CHAT_DM_FANOUT_CHANNEL)
        log.info("chat dm pubsub subscribed channel=%s", CHAT_DM_FANOUT_CHANNEL)
        while not stop_event.is_set():
            try:
                msg = await pubsub.get_message(
                    ignore_subscribe_messages=True,
                    timeout=_MESSAGE_POLL_TIMEOUT_SEC,
                )
            except asyncio.CancelledError:
                raise
            except Exception:
                log.exception("chat pubsub get_message 실패, 잠시 대기 후 재시도")
                await asyncio.sleep(0.5)
                continue
            if msg is None:
                continue
            if msg.get("type") != "message":
                continue
            raw = msg.get("data")
            if isinstance(raw, bytes):
                raw = raw.decode("utf-8")
            if not isinstance(raw, str) or not raw:
                continue
            parsed = _parse_envelope(raw)
            if parsed is None:
                continue
            target_user_id, payload = parsed
            try:
                await chat_connection_manager.send_personal_message(target_user_id, payload)
            except Exception:
                log.exception("chat local fanout 실패 user=%s", target_user_id)
    except asyncio.CancelledError:
        raise
    except Exception:
        log.exception("chat pubsub listener 종료 예외")
    finally:
        if pubsub is not None:
            try:
                await pubsub.unsubscribe(CHAT_DM_FANOUT_CHANNEL)
            except Exception:
                log.exception("chat pubsub unsubscribe 실패")
            try:
                await pubsub.aclose()
            except Exception:
                log.exception("chat pubsub aclose 실패")
        if client is not None:
            try:
                await client.aclose()
            except Exception:
                log.exception("chat pubsub redis aclose 실패")
