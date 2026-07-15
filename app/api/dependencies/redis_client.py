# 앱 lifespan에 붙은 Redis 클라이언트 조회 의존성. 없으면 None (fail-open 경로).

from fastapi import Request

from app.infra.redis import RedisLike, get_app_redis


def get_optional_redis(request: Request) -> RedisLike | None:
    return get_app_redis(request.app)
