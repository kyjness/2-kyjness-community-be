"""클라이언트 식별자(조회수 dedup·signup 멱등 스코프) 단위 테스트.

불변식: 원시 X-Forwarded-For 헤더는 신뢰하지 않는다 — 신뢰 프록시 검증을 통과한
scope["client"]만 쓴다. 위조 XFF로 viewer_key를 요청마다 바꿔 조회수를 부풀리는
경로를 차단한다(ProxyHeadersMiddleware·rate limit 키 산정과 동일 규약).
"""

from app.api.dependencies.client import get_client_identifier
from starlette.requests import Request


def _request(client: tuple[str, int] | None, headers: list[tuple[bytes, bytes]]) -> Request:
    scope = {
        "type": "http",
        "method": "GET",
        "path": "/",
        "headers": headers,
        "client": client,
    }
    return Request(scope)


def test_spoofed_xff_header_is_ignored():
    req = _request(("203.0.113.9", 12345), [(b"x-forwarded-for", b"6.6.6.6, 10.0.0.1")])
    assert get_client_identifier(req) == "203.0.113.9"


def test_uses_scope_client_without_headers():
    req = _request(("198.51.100.4", 443), [])
    assert get_client_identifier(req) == "198.51.100.4"


def test_missing_client_falls_back_to_zero_address():
    req = _request(None, [(b"x-forwarded-for", b"6.6.6.6")])
    assert get_client_identifier(req) == "0.0.0.0"


def test_trusted_proxy_rewritten_scope_is_honored():
    # ProxyHeadersMiddleware가 신뢰 프록시 검증 후 scope["client"]를 실제 IP로 갱신한 상태를 모사.
    # 식별자는 그 갱신값을 그대로 쓴다(헤더 재파싱 없음).
    req = _request(("203.0.113.77", 0), [(b"x-forwarded-for", b"203.0.113.77, 10.0.0.1")])
    assert get_client_identifier(req) == "203.0.113.77"
