# Redis 연결. Rate Limit·Refresh Token 저장. 앱 lifespan에서 init/close.
import logging
from collections.abc import Awaitable
from typing import Any, Protocol, runtime_checkable

from redis.asyncio import ConnectionPool, Redis

from app.core.config import settings

log = logging.getLogger(__name__)


@runtime_checkable
class RedisLike(Protocol):
    """앱이 사용하는 Redis 명령의 구조적 계약 — isinstance 가드는 혈통(실클라이언트
    상속)이 아니라 이 능력 집합을 검사한다. 테스트 가짜가 Redis를 상속할 필요가
    없어져, 상속 시그니처 충돌을 가리던 로컬 스텁(typings/) 없이 업스트림 타입
    그대로 검사받는다.

    파라미터는 positional-only(/)로 선언해 redis-py의 파라미터 이름(name=…)과의
    표기 차이를 계약에서 배제하고, 반환은 Any — redis-py 명령이 동기/비동기 겸용
    유니온(`Awaitable[T] | T`)을 반환해 좁은 반환 타입은 실클라이언트와 어긋난다.
    호출부는 항상 await한다. 멤버는 실사용 명령만 — 넓힐 때는 호출부 추가와
    함께 여기에 등록한다(runtime_checkable isinstance는 멤버 수에 비례).
    """

    def ping(self) -> Any: ...
    def aclose(self) -> Awaitable[None]: ...
    def get(self, key: str, /) -> Any: ...
    def set(self, key: str, value: Any, /, *, nx: bool = ..., ex: int | None = ...) -> Any: ...
    def setex(self, key: str, seconds: int, value: Any, /) -> Any: ...
    def delete(self, *keys: str) -> Any: ...
    def eval(self, script: str, numkeys: int, /, *args: Any) -> Any: ...
    def hget(self, key: str, field: str, /) -> Any: ...
    def hgetall(self, key: str, /) -> Any: ...
    def hincrby(self, key: str, field: str, amount: int, /) -> Any: ...
    def publish(self, channel: str, message: str, /) -> Any: ...
    def pubsub(self) -> Any: ...


def get_app_redis(app: Any) -> RedisLike | None:
    """앱 lifespan에 붙은 클라이언트 조회의 단일 창구. 미초기화·비Redis 값은 None(fail-open).

    bare getattr는 isinstance 가드가 없어 잘못된 state 주입이 하류에서 AttributeError로
    터진다 — 접근자를 한 곳으로 모아 가드·계약을 통일한다.
    """
    raw = getattr(app.state, "redis", None) if app is not None else None
    return raw if isinstance(raw, RedisLike) else None


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
        # RedisLike 주석은 실클라이언트가 Protocol 계약을 만족하는지 타입 수준에서 강제한다.
        client: RedisLike = Redis(connection_pool=pool)
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
    if isinstance(client, RedisLike):
        # connection_pool은 실클라이언트 전용이라 Protocol 계약 밖 — getattr로 유무만 본다.
        pool = getattr(client, "connection_pool", None)
        await client.aclose()
        if pool is not None:
            await pool.disconnect()
        app.state.redis = None
        log.info("Redis connection closed.")
