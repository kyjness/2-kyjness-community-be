# Redis 기반 분산 Rate Limit. Lua로 INCR+EXPIRE+TTL 원자 수행.
# 순수 ASGI 미들웨어(scope/receive/send). Redis 장애 시 로그인/회원가입 업로드에 한해 In-memory Fallback(스마트 Fail-open).
# 함수형 래퍼 없음. main에서 add_middleware(RateLimitMiddleware)로 등록.
import json
import logging
import time
from typing import Any

from redis.asyncio import Redis
from starlette.types import ASGIApp, Receive, Scope, Send

from app.common import ApiCode
from app.common.paths import (
    HEALTH_PATH,
    LOGIN_PATH,
    SIGNUP_CONFIRM_PATH,
    SIGNUP_PRESIGN_PATH,
)
from app.core.config import settings
from app.core.metrics import RATE_LIMIT_REJECTIONS
from app.infra.redis import get_app_redis

logger = logging.getLogger(__name__)

# 프로브·계측 경로는 한도 제외. /livez·/readyz·/metrics는 앱 루트, health는 API prefix 아래.
_SKIP_PATHS = frozenset({HEALTH_PATH, "/livez", "/readyz", "/metrics"})
_KEY_PREFIX = "rl"

# In-memory Fallback: 최대 10,000키, OOM 방지 eviction.
_MEMORY_MAX_KEYS = 10_000
_memory_store: dict[str, tuple[int, float]] = {}

_LUA_FIXED_WINDOW = """
local c = redis.call('INCR', KEYS[1])
if c == 1 then
    redis.call('EXPIRE', KEYS[1], ARGV[1])
end
local ttl = redis.call('TTL', KEYS[1])
return {c, ttl}
"""


def _redis_from_scope(scope: Scope) -> Redis | None:
    """Starlette가 매 요청 scope["app"]에 심는 앱 인스턴스에서 redis를 얻는다.

    미들웨어 체인 객체를 .app으로 거슬러 올라가는 방식은 어떤 노드도 .state를
    갖지 않아 항상 None이 나온다(분산 rate limit이 조용히 비활성화되는 결함).
    """
    return get_app_redis(scope.get("app"))


def get_client_ip_from_scope(scope: Scope) -> str:
    """scope['client'] 사용. proxy_headers 미들웨어가 이미 실제 IP로 갱신한 상태를 가정."""
    client = scope.get("client")
    if client:
        return client[0]
    return "unknown"


def _path_is_login(path: str) -> bool:
    return path.rstrip("/") == LOGIN_PATH


def _path_is_signup_upload(path: str) -> bool:
    """비인증 회원가입 업로드 경로(presign·confirm 2단). 글로벌 100/분만으로는 비로그인
    IP가 presign을 대량 발급받아 pending/ 객체를 쌓을 수 있어 전용 한도로 조인다."""
    p = path.rstrip("/")
    return p in (SIGNUP_PRESIGN_PATH, SIGNUP_CONFIRM_PATH)


def _is_critical_path(path: str) -> bool:
    """Redis 장애 시 In-memory Fallback을 적용할 중요 경로(로그인·회원가입 업로드)."""
    return _path_is_login(path) or _path_is_signup_upload(path)


def _memory_evict_if_needed(now: float) -> None:
    """저장소가 최대 키 수 이상이면: 만료된 키 삭제 후, 여전히 초과 시 window_end_ts가 가장 작은 키 삭제."""
    if len(_memory_store) < _MEMORY_MAX_KEYS:
        return
    expired = [k for k, (_, end) in _memory_store.items() if end < now]
    for k in expired:
        del _memory_store[k]
    while len(_memory_store) >= _MEMORY_MAX_KEYS and _memory_store:
        oldest_key = min(_memory_store.keys(), key=lambda k: _memory_store[k][1])
        del _memory_store[oldest_key]


def _check_memory_fixed_window(key: str, window_sec: int, max_count: int) -> tuple[bool, int]:
    """In-memory Fixed Window. (allowed, retry_after_seconds)."""
    now = time.monotonic()
    _memory_evict_if_needed(now)
    if key not in _memory_store:
        _memory_store[key] = (1, now + window_sec)
        return True, 0
    count, window_end = _memory_store[key]
    if now >= window_end:
        _memory_store[key] = (1, now + window_sec)
        return True, 0
    count += 1
    _memory_store[key] = (count, window_end)
    if count > max_count:
        retry_after = max(0, int(window_end - now))
        return False, retry_after
    return True, 0


async def _check_redis_fixed_window(
    redis: Redis,
    key: str,
    window_sec: int,
    max_count: int,
) -> tuple[bool, int]:
    full_key = f"{_KEY_PREFIX}:{key}"
    try:
        result: Any = await redis.eval(_LUA_FIXED_WINDOW, 1, full_key, window_sec)
        count, ttl = int(result[0]), int(result[1])
        retry_after = max(0, ttl) if ttl >= 0 else window_sec
        if count > max_count:
            return False, retry_after
        return True, 0
    except Exception as e:
        logger.warning("Rate limit Redis 오류: %s. Fallback 또는 통과.", e)
        raise


async def check_fixed_window(
    redis: Redis | None,
    key: str,
    *,
    window_sec: int,
    max_count: int,
    fail_open: bool = False,
) -> tuple[bool, int]:
    """fixed-window 검사 단일 진입점(미들웨어·WS 수신 루프 공용). (allowed, retry_after).

    Redis 우선(멀티 인스턴스 공유 한도). Redis 부재·장애 시: `fail_open=True`면 통과
    (글로벌 한도 — 가용성 우선), False면 인스턴스 로컬 메모리 윈도로 폴백(로그인·업로드·
    WS 같은 남용 방어 경로 — 근사 한도라도 유지).

    key는 `종류:식별자` 규약 — 첫 콜론 앞이 거부 메트릭의 limit 라벨이 되므로
    카디널리티가 유한한 접두사를 쓸 것(login·signup_upload·global·chat 등).
    """
    allowed = True
    retry_after = 0
    if redis is not None:
        try:
            allowed, retry_after = await _check_redis_fixed_window(
                redis, key, window_sec, max_count
            )
        except Exception:
            if not fail_open:
                allowed, retry_after = _check_memory_fixed_window(key, window_sec, max_count)
    elif not fail_open:
        allowed, retry_after = _check_memory_fixed_window(key, window_sec, max_count)
    if not allowed:
        count_rejection(key.split(":", 1)[0])
    return allowed, retry_after


def count_rejection(limit: str) -> None:
    """거부 계측 단일 창구. check_fixed_window를 거치지 않는 거부(WS 억제 창의 로컬
    즉시 거부 등)도 반드시 이 함수로 센다 — 아니면 스팸 급증 구간에서 메트릭이
    거부의 대부분을 놓쳐 대시보드가 '한도가 거의 안 걸린다'고 오판하게 된다."""
    RATE_LIMIT_REJECTIONS.labels(limit=limit).inc()


async def _send_429(send: Send, scope: Scope, code: ApiCode, retry_after_seconds: int) -> None:
    """순수 ASGI: 429 응답만 전송. ApiResponse·전역 에러와 동일 키(requestId 등)."""
    state = scope.get("state") or {}
    rid = state.get("request_id", "") or ""
    body = json.dumps(
        {
            "code": code.value,
            "message": "",
            "data": {"retry_after_seconds": retry_after_seconds},
            "requestId": rid,
        },
        ensure_ascii=False,
    ).encode("utf-8")
    headers = [
        (b"content-type", b"application/json"),
        (b"retry-after", str(retry_after_seconds).encode()),
    ]
    await send(
        {
            "type": "http.response.start",
            "status": 429,
            "headers": headers,
        }
    )
    await send({"type": "http.response.body", "body": body})


class RateLimitMiddleware:
    """순수 ASGI 미들웨어. BaseHTTPMiddleware 미사용. scope/receive/send만 사용."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        path = scope.get("path", "")
        method = scope.get("method", "GET")
        if method == "OPTIONS" or path in _SKIP_PATHS:
            await self.app(scope, receive, send)
            return

        ip = get_client_ip_from_scope(scope)
        redis: Redis | None = _redis_from_scope(scope)

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

        # 정책(Redis 우선·폴백·거부 메트릭)은 check_fixed_window 한 곳 — 글로벌 한도만
        # Redis 장애 시 fail-open, 로그인·회원가입 업로드는 메모리 폴백으로 방어 유지.
        allowed, retry_after_seconds = await check_fixed_window(
            redis,
            key,
            window_sec=window,
            max_count=max_count,
            fail_open=not _is_critical_path(path),
        )
        if not allowed:
            await _send_429(send, scope, code, retry_after_seconds)
            return

        await self.app(scope, receive, send)


def get_client_ip(request: Any) -> str:
    """프록시 검증이 끝난 request.client 사용. scope가 있으면 get_client_ip_from_scope 활용."""
    if getattr(request, "client", None):
        return request.client[0]
    scope = getattr(request, "scope", None)
    if scope:
        return get_client_ip_from_scope(scope)
    return "unknown"
