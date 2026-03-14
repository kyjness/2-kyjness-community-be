# Redis 연결. Rate Limit·Refresh Token 저장. 앱 lifespan에서 init/close.
import logging

from redis.asyncio import ConnectionPool, Redis

from app.core.config import settings

log = logging.getLogger(__name__)


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
        log.info("Redis connection pool initialized.")
    except Exception as e:
        log.warning("Redis 연결 실패: %s. Rate limit 미들웨어는 Fail-open.", e)
        app.state.redis = None


async def close_redis(app) -> None:
    client = getattr(app.state, "redis", None)
    if isinstance(client, Redis):
        await client.aclose()
        app.state.redis = None
        log.info("Redis connection closed.")
