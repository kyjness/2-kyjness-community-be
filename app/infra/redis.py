# Redis 연결. Rate Limit·Refresh Token 저장. 앱 lifespan에서 init/close.
import logging
from typing import Any, cast

from redis.asyncio import ConnectionPool, Redis

from app.core.config import settings

log = logging.getLogger(__name__)


def get_app_redis(app: Any) -> Redis | None:
    """앱 lifespan에 붙은 클라이언트 조회의 단일 창구. 미초기화·비Redis 값은 None(fail-open).

    bare getattr는 isinstance 가드가 없어 잘못된 state 주입이 하류에서 AttributeError로
    터진다 — 접근자를 한 곳으로 모아 가드·계약을 통일한다.
    """
    raw = getattr(app.state, "redis", None) if app is not None else None
    return raw if isinstance(raw, Redis) else None


def bulk_to_str(value: Any) -> str | None:
    """Redis GET 결과(bytes/str)를 비교용 문자열로 통일한다."""
    if value is None:
        return None
    if isinstance(value, (bytes, bytearray)):
        return value.decode("utf-8")
    return str(value)


async def init_redis(app) -> None:
    app.state.redis = None
    if not settings.REDIS_URL:
        return
    try:
        pool = ConnectionPool.from_url(
            settings.REDIS_URL,
            max_connections=settings.REDIS_MAX_CONNECTIONS,
            decode_responses=True,
        )
        client: Redis = Redis(connection_pool=pool)
        app.state.redis = client
        await client.ping()
        log.info(
            "Redis connection pool initialized (max_connections=%s).",
            settings.REDIS_MAX_CONNECTIONS,
        )
    except Exception as e:
        log.warning("Redis 연결 실패: %s. Rate limit 미들웨어는 Fail-open.", e)
        app.state.redis = None


async def close_redis(app) -> None:
    client = getattr(app.state, "redis", None)
    if isinstance(client, Redis):
        c = cast(Any, client)
        pool = c.connection_pool
        await c.aclose()
        if pool is not None:
            await pool.disconnect()
        app.state.redis = None
        log.info("Redis connection closed.")
