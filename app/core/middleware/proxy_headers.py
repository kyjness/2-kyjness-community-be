# Nginx/ALB 뒤에서 실제 클라이언트 IP를 scope['client']에 반영. 신뢰 프록시 IP 대역에서만 X-Forwarded-For 파싱(IP 스푸핑 방어).
import ipaddress

from starlette.types import ASGIApp, Receive, Scope, Send

from app.core.config import settings


def _is_trusted_proxy(direct_client_ip: str, allowed: list[str]) -> bool:
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


class ProxyHeadersMiddleware:
    """순수 ASGI. X-Forwarded-For 검증 후 scope['client'] 갱신. add_middleware 시 RateLimit보다 바깥에 두어 먼저 실행."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        if settings.TRUST_X_FORWARDED_FOR:
            client = scope.get("client") or ("", 0)
            if _is_trusted_proxy(client[0], settings.TRUSTED_PROXY_IPS):
                for raw_name, raw_val in scope.get("headers") or []:
                    if raw_name.lower() == b"x-forwarded-for" and raw_val:
                        forwarded = raw_val.decode("utf-8", errors="replace").strip()
                        if forwarded:
                            scope["client"] = (forwarded.split(",")[0].strip(), 0)
                        break
        await self.app(scope, receive, send)
