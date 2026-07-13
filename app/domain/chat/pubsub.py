# DM 채팅 분산 브로드캐스트: 단일 Pub/Sub 채널 + envelope에 수신자 UUID.
# 구독·디스패치는 app.infra.pubsub의 공용 리스너(인스턴스당 전용 연결 1개)가 수행한다.

from uuid import UUID

from redis.asyncio import Redis

from app.infra.pubsub import publish_user_envelope

# 알림 puppytalk:channel:notif:sse 와 네임스페이스 분리. 단일 채널이라 클러스터 슬롯 이슈 없음.
CHAT_DM_FANOUT_CHANNEL = "puppytalk:channel:chat:dm"


async def publish_chat_dm(
    redis: Redis | None,
    *,
    target_user_id: UUID,
    payload: str,
) -> bool:
    """다른 인스턴스로 DM envelope 전달. 같은 인스턴스 수신자는 호출 전에 로컬 매니저로
    이미 직접 전달돼 있어야 한다(리스너가 origin으로 자기 발행분을 스킵). 반환값은
    크로스 인스턴스 발행 성공 여부 — 실패 시 다른 인스턴스 수신자만 유실(at-most-once)."""
    return await publish_user_envelope(
        redis,
        CHAT_DM_FANOUT_CHANNEL,
        target_user_id=target_user_id,
        payload=payload,
    )
