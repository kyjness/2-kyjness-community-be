# Nginx/ALB 뒤에서 실제 클라이언트 IP를 request.client에 반영. 신뢰 프록시 IP 대역에서 온 요청일 때만 X-Forwarded-For 파싱(IP 스푸핑 방어).
import ipaddress
from typing import Awaitable, Callable, List

from starlette.requests import Request
from starlette.responses import Response

from app.core.config import settings


def _is_trusted_proxy(direct_client_ip: str, allowed: List[str]) -> bool:
    if not allowed:
        return True
    try:
        client = ipaddress.ip_address(direct_client_ip)
    except ValueError:
        return False
    for item in allowed:
        item = item.strip()
        if not item:
            continue
        try:
            if "/" in item:
                if client in ipaddress.ip_network(item, strict=False):
                    return True
            else:
                if client == ipaddress.ip_address(item):
                    return True
        except ValueError:
            continue
    return False


async def proxy_headers_middleware(
    request: Request,
    call_next: Callable[[Request], Awaitable[Response]],
) -> Response:
    if not settings.TRUST_X_FORWARDED_FOR:
        return await call_next(request)
    direct_client = (request.scope.get("client") or ("", 0))[0]
    if not _is_trusted_proxy(direct_client, settings.TRUSTED_PROXY_IPS):
        return await call_next(request)
    forwarded = request.headers.get("x-forwarded-for") or request.headers.get("X-Forwarded-For")
    if forwarded:
        client_ip = forwarded.split(",")[0].strip()
        request.scope["client"] = (client_ip, 0)
    return await call_next(request)
