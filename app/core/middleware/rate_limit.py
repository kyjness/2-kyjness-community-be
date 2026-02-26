import asyncio
import time
from collections import deque
from typing import Awaitable, Callable

from fastapi import Request
from starlette.responses import Response

from app.core.config import settings
from app.common import ApiCode, raise_http_error

_request_times: dict[str, deque[float]] = {}
_login_attempt_times: dict[str, deque[float]] = {}
_signup_upload_times: dict[str, deque[float]] = {}
_lock = asyncio.Lock()
_login_lock = asyncio.Lock()
_signup_upload_lock = asyncio.Lock()

_SKIP_PATHS = frozenset({"/health"})


def get_client_ip(request: Request) -> str:
    if settings.TRUST_X_FORWARDED_FOR:
        forwarded = request.headers.get("x-forwarded-for")
        if forwarded:
            return forwarded.split(",")[0].strip()
    if request.client:
        return request.client.host
    return "unknown"


async def _memory_login_check(request: Request) -> bool:
    ip = get_client_ip(request)
    now = time.monotonic()
    window = settings.LOGIN_RATE_LIMIT_WINDOW
    max_attempts = settings.LOGIN_RATE_LIMIT_MAX_ATTEMPTS
    async with _login_lock:
        times = _login_attempt_times.get(ip)
        if times is None:
            times = deque()
            _login_attempt_times[ip] = times
        cutoff = now - window
        while times and times[0] < cutoff:
            times.popleft()
        if not times and ip in _login_attempt_times:
            del _login_attempt_times[ip]
        if len(times) >= max_attempts:
            return True
        _login_attempt_times[ip] = times
        times.append(now)
    return False


async def check_login_rate_limit(request: Request) -> None:
    if await _memory_login_check(request):
        raise_http_error(429, ApiCode.LOGIN_RATE_LIMIT_EXCEEDED)


async def _memory_signup_upload_check(request: Request) -> bool:
    ip = get_client_ip(request)
    now = time.monotonic()
    window = settings.SIGNUP_UPLOAD_RATE_LIMIT_WINDOW
    max_uploads = settings.SIGNUP_UPLOAD_RATE_LIMIT_MAX
    async with _signup_upload_lock:
        times = _signup_upload_times.get(ip)
        if times is None:
            times = deque()
            _signup_upload_times[ip] = times
        cutoff = now - window
        while times and times[0] < cutoff:
            times.popleft()
        if not times and ip in _signup_upload_times:
            del _signup_upload_times[ip]
        if len(times) >= max_uploads:
            return True
        _signup_upload_times[ip] = times
        times.append(now)
    return False


async def check_signup_upload_rate_limit(request: Request) -> None:
    if await _memory_signup_upload_check(request):
        raise_http_error(429, ApiCode.RATE_LIMIT_EXCEEDED)


async def _memory_global_check(request: Request) -> bool:
    ip = get_client_ip(request)
    now = time.monotonic()
    window = settings.RATE_LIMIT_WINDOW
    max_requests = settings.RATE_LIMIT_MAX_REQUESTS
    async with _lock:
        times = _request_times.get(ip)
        if times is None:
            times = deque()
            _request_times[ip] = times
        cutoff = now - window
        while times and times[0] < cutoff:
            times.popleft()
        if not times and ip in _request_times:
            del _request_times[ip]
        if len(times) >= max_requests:
            return True
        _request_times[ip] = times
        times.append(now)
    return False


async def rate_limit_middleware(
    request: Request,
    call_next: Callable[[Request], Awaitable[Response]],
) -> Response:
    if request.url.path in _SKIP_PATHS:
        return await call_next(request)
    if await _memory_global_check(request):
        raise_http_error(429, ApiCode.RATE_LIMIT_EXCEEDED)
    return await call_next(request)
