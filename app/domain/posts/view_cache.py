# 조회수 중복 방지: IP(또는 식별자) + postId 기준 인메모리 캐시, TTL 24시간.
import os
import threading
import time
from starlette.requests import Request

# 개발 시 0으로 설정하면 캐시 비사용(매 방문 시 조회수 +1). 기본 24시간.
VIEW_TTL_SECONDS = int(os.getenv("VIEW_CACHE_TTL_SECONDS", str(24 * 3600)))
_cache: dict[str, float] = {}
_lock = threading.Lock()


def get_client_identifier(request: Request) -> str:
    """프록시 환경 고려: X-Forwarded-For 첫 값, 없으면 request.client.host."""
    forwarded = request.headers.get("x-forwarded-for") or request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip() or "0.0.0.0"
    client = request.scope.get("client") or ("0.0.0.0", 0)
    return (client[0] or "0.0.0.0").strip()


def view_cache_key(post_id: int, identifier: str) -> str:
    return f"view:post:{post_id}:ip:{identifier}"


def consume_view_if_new(post_id: int, identifier: str) -> bool:
    """
    캐시 Hit면 False(DB 증가 스킵), Miss면 캐시 등록 후 True(DB 증가 수행).
    VIEW_TTL_SECONDS가 0이면 캐시 미사용(항상 True, 매 방문 시 +1).
    """
    if VIEW_TTL_SECONDS <= 0:
        return True
    key = view_cache_key(post_id, identifier)
    now = time.time()
    expiry = now + VIEW_TTL_SECONDS
    with _lock:
        if key in _cache and _cache[key] > now:
            return False
        _cache[key] = expiry
        return True
