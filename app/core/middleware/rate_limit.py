# Redis 기반 분산 Rate Limit. Lua로 INCR+EXPIRE+TTL 원자 수행, 비차단, Fail-open.
import logging
from typing import Awaitable, Callable, Optional, Tuple

from fastapi import Request
from redis.asyncio import Redis
from starlette.responses import JSONResponse, Response

from app.common import ApiCode
from app.core.config import settings

logger = logging.getLogger(__name__)

_SKIP_PATHS = frozenset({"/health"})
_KEY_PREFIX = "rl"

# Fixed Window: INCR → (count==1이면 EXPIRE) → TTL 반환. 한 번에 원자 수행.
_LUA_FIXED_WINDOW = """
local c = redis.call('INCR', KEYS[1])
if c == 1 then
    redis.call('EXPIRE', KEYS[1], ARGV[1])
end
local ttl = redis.call('TTL', KEYS[1])
return {c, ttl}
"""


def get_client_ip(request: Request) -> str:
    """프록시 검증이 끝난 request.client만 사용. X-Forwarded-For 직접 파싱 금지(proxy_headers 미들웨어가 이미 scope['client'] 갱신)."""
    if request.client:
        return request.client.host
    return "unknown"


def _get_redis(request: Request) -> Optional[Redis]:
    return getattr(request.app.state, "redis", None)


async def _check_fixed_window(
    redis: Redis,
    key: str,
    window_sec: int,
    max_count: int,
) -> Tuple[bool, int]:
    full_key = f"{_KEY_PREFIX}:{key}"
    try:
        result = await redis.eval(_LUA_FIXED_WINDOW, 1, full_key, window_sec)
        count, ttl = int(result[0]), int(result[1])
        retry_after = max(0, ttl) if ttl >= 0 else window_sec
        if count > max_count:
            return False, retry_after
        return True, 0
    except Exception as e:
        logger.warning("Rate limit Redis 오류: %s. 요청 허용(Fail-open).", e)
        return True, 0


def _path_is_login(path: str) -> bool:
    p = path.rstrip("/")
    return p == "/v1/auth/login" or p.endswith("/auth/login")


def _path_is_signup_upload(path: str) -> bool:
    p = path.rstrip("/")
    return p == "/v1/media/images/signup" or p.endswith("/media/images/signup")


async def rate_limit_middleware(
    request: Request,
    call_next: Callable[[Request], Awaitable[Response]],
) -> Response:
    """Redis 없거나 예외 시 call_next(Fail-open). OPTIONS·/health 제외. 경로별 키·제한 적용."""
    if request.method == "OPTIONS":
        return await call_next(request)
    if request.url.path in _SKIP_PATHS:
        return await call_next(request)

    redis = _get_redis(request)
    if redis is None:
        return await call_next(request)

    ip = get_client_ip(request)
    path = request.url.path

    if _path_is_login(path):
        key = f"login:{ip}"
        window = settings.LOGIN_RATE_LIMIT_WINDOW
        max_count = settings.LOGIN_RATE_LIMIT_MAX_ATTEMPTS
        code = ApiCode.LOGIN_RATE_LIMIT_EXCEEDED
    elif _path_is_signup_upload(path):
        key = f"signup_upload:{ip}"
        window = settings.SIGNUP_UPLOAD_RATE_LIMIT_WINDOW
        max_count = settings.SIGNUP_UPLOAD_RATE_LIMIT_MAX
        code = ApiCode.RATE_LIMIT_EXCEEDED
    else:
        key = f"global:{ip}"
        window = settings.RATE_LIMIT_WINDOW
        max_count = settings.RATE_LIMIT_MAX_REQUESTS
        code = ApiCode.RATE_LIMIT_EXCEEDED

    allowed, retry_after_seconds = await _check_fixed_window(redis, key, window, max_count)
    if allowed:
        return await call_next(request)

    return JSONResponse(
        status_code=429,
        content={
            "code": code.value,
            "data": {"retry_after_seconds": retry_after_seconds},
        },
        headers={"Retry-After": str(retry_after_seconds)},
    )
