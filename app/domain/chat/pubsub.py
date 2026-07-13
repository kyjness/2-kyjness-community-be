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
    """다른 워커/프로세스로 DM 페이로드 전달. False면 호출부가 로컬 전달로 폴백해야 한다."""
    return await publish_user_envelope(
        redis,
        CHAT_DM_FANOUT_CHANNEL,
        target_user_id=target_user_id,
        payload=payload,
    )
