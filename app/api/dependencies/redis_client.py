# 앱 lifespan에 붙은 Redis 클라이언트 조회. 없으면 None (fail-open 경로).
from __future__ import annotations

from fastapi import Request
from redis.asyncio import Redis


def get_optional_redis(request: Request) -> Redis | None:
    raw = getattr(request.app.state, "redis", None)
    return raw if isinstance(raw, Redis) else None
