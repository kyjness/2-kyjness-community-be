# 유저 대상 실시간 팬아웃 공용 인프라: 단일 채널 + envelope(수신자 UUID) 발행,
# 인스턴스당 전용 Pub/Sub 연결 1개로 여러 채널을 구독해 로컬 핸들러로 디스패치.
#
# 연결마다 공유 풀에서 pubsub을 점유하면 동시 구독자 수가 풀 한도를 잠식해
# rate limit·인증 캐시·조회수 버퍼가 연쇄 fail-open된다 — 구독 소켓은 프로세스당
# 1개로 고정하고, 수신자별 분기는 로컬 매니저(chat WS·알림 SSE)가 맡는다.
#
# 전달 규약: 발행자는 같은 인스턴스 수신자에게 로컬 매니저로 먼저 직접 전달한 뒤
# publish한다(로컬 전달이 Redis·리스너 상태에 의존하지 않게). 리스너는 envelope의
# origin이 자기 인스턴스면 건너뛰어 중복 전달을 막는다.

import asyncio
import json
import logging
from collections.abc import Awaitable, Callable
from typing import Any, cast
from uuid import UUID, uuid4

from redis.asyncio import Redis

log = logging.getLogger(__name__)

_MESSAGE_POLL_TIMEOUT_SEC = 1.0

# 리스너가 죽으면 해당 인스턴스의 크로스 인스턴스 실시간 전달이 프로세스 재시작까지
# 전멸한다(멀티 인스턴스·99.9% 전제에서 미수용) — 연결 실패·수신 오류는 백오프 재연결.
_RECONNECT_BACKOFF_INITIAL_SEC = 0.5
_RECONNECT_BACKOFF_MAX_SEC = 30.0

# envelope origin — 리스너가 자기 발행분을 식별해 건너뛴다.
_INSTANCE_ID = str(uuid4())

# (target_user_id, payload) → 로컬 전달. payload는 클라이언트에 그대로 보낼 텍스트.
UserEnvelopeHandler = Callable[[UUID, str], Awaitable[None]]


async def publish_user_envelope(
    redis: Redis | None,
    channel: str,
    *,
    target_user_id: UUID,
    payload: str,
) -> bool:
    """envelope PUBLISH(크로스 인스턴스 전달). 성공 여부를 반환한다 — 예외는 여기서
    삼키므로 반환값이 유일한 실패 신호. 같은 인스턴스 수신자는 발행 전에 로컬 매니저로
    직접 전달돼 있어야 한다(publish 실패는 다른 인스턴스 수신자만 유실, at-most-once)."""
    if redis is None or not payload:
        return False
    env = json.dumps(
        {"origin": _INSTANCE_ID, "target_user_id": str(target_user_id), "payload": payload},
        ensure_ascii=False,
    )
    try:
        r = cast(Any, redis)
        await r.publish(channel, env)
        return True
    except Exception:
        log.exception("pubsub publish 실패 channel=%s", channel)
        return False


def parse_user_envelope(raw: str) -> tuple[UUID, str, str | None] | None:
    """(target_user_id, payload, origin). payload가 문자열이 아니면 규약 위반 — 버린다."""
    try:
        data = json.loads(raw)
        uid = UUID(str(data["target_user_id"]))
        payload = data["payload"]
        if not isinstance(payload, str):
            log.warning("pubsub envelope payload가 str이 아님", exc_info=False)
            return None
        origin = data.get("origin")
        return uid, payload, origin if isinstance(origin, str) else None
    except Exception:
        log.warning("pubsub envelope invalid", exc_info=False)
        return None


async def _dispatch_message(msg: Any, handlers: dict[str, UserEnvelopeHandler]) -> None:
    if msg.get("type") != "message":
        return
    channel = msg.get("channel")
    handler = handlers.get(channel) if isinstance(channel, str) else None
    if handler is None:
        return
    raw = msg.get("data")
    if not isinstance(raw, str) or not raw:
        return
    parsed = parse_user_envelope(raw)
    if parsed is None:
        return
    target_user_id, payload, origin = parsed
    if origin == _INSTANCE_ID:
        return  # 자기 발행분 — 로컬 수신자는 발행 시점에 이미 직접 전달됨
    try:
        await handler(target_user_id, payload)
    except Exception:
        log.exception("local fanout 실패 channel=%s user=%s", channel, target_user_id)


async def _listen_once(
    *,
    redis_url: str,
    handlers: dict[str, UserEnvelopeHandler],
    stop_event: asyncio.Event,
    on_healthy: Callable[[], None],
) -> None:
    """연결 1회분: 접속→구독→폴링. 연결·수신 계층 예외는 밖으로 던져 재연결을 유도하고,
    핸들러·envelope 오류는 삼킨다(메시지 1건 문제로 연결을 버리지 않는다).

    `on_healthy`는 구독 직후가 아니라 **첫 폴이 성공한 뒤** 호출한다 — 구독만 되고 바로
    죽는 플래핑 연결이 백오프를 계속 초기값으로 되돌려 0.5s 고정 재연결 루프에 빠지는 것 방지.
    """
    client: Any = None
    pubsub: Any = None
    try:
        # redis.asyncio 타입 스텁에 from_url 미정의 → 런타임 팩토리만 사용.
        client = cast(Any, Redis).from_url(redis_url, decode_responses=True)
        await client.ping()
        pubsub = client.pubsub()
        await pubsub.subscribe(*handlers)
        log.info("user fanout pubsub subscribed channels=%s", sorted(handlers))
        healthy_signaled = False
        while not stop_event.is_set():
            msg = await pubsub.get_message(
                ignore_subscribe_messages=True,
                timeout=_MESSAGE_POLL_TIMEOUT_SEC,
            )
            if not healthy_signaled:
                on_healthy()
                healthy_signaled = True
            if msg is None:
                continue
            await _dispatch_message(msg, handlers)
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


async def run_user_fanout_listener(
    *,
    redis_url: str,
    handlers: dict[str, UserEnvelopeHandler],
    stop_event: asyncio.Event,
) -> None:
    """백그라운드: 전용 Redis 연결 1개로 `handlers`의 모든 채널을 구독하고,
    수신 envelope를 채널별 핸들러로 로컬 팬아웃한다. 연결이 끊기면 백오프 재연결."""
    if not redis_url or not handlers:
        return
    backoff = _RECONNECT_BACKOFF_INITIAL_SEC

    def _reset_backoff() -> None:
        nonlocal backoff
        backoff = _RECONNECT_BACKOFF_INITIAL_SEC

    while not stop_event.is_set():
        try:
            await _listen_once(
                redis_url=redis_url,
                handlers=handlers,
                stop_event=stop_event,
                on_healthy=_reset_backoff,
            )
        except asyncio.CancelledError:
            raise
        except Exception:
            log.exception("pubsub 리스너 연결 유실, %.1fs 후 재연결", backoff)
        try:
            await asyncio.wait_for(stop_event.wait(), timeout=backoff)
            break
        except TimeoutError:
            pass
        backoff = min(backoff * 2, _RECONNECT_BACKOFF_MAX_SEC)
