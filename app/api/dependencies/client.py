# 요청 기반 클라이언트 식별자. 조회수 중복 방지 등에서 사용.
from fastapi import Request


def get_client_identifier(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for") or request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip() or "0.0.0.0"
    client = request.scope.get("client") or ("0.0.0.0", 0)
    return (client[0] or "0.0.0.0").strip()
