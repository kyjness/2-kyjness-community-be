# 요청 기반 클라이언트 식별자. 조회수 중복 방지 등에서 사용.
# Redis 멱등성: 네임스페이스·fingerprint_scope_parts로 도메인 분리.
import hashlib
import json
import logging
from typing import Any
from uuid import UUID

from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import TypeAdapter, ValidationError
from redis.asyncio import Redis

from app.common.codes import ApiCode
from app.common.responses import get_request_id
from app.common.schemas import ApiResponse
from app.core.config import settings
from app.domain.posts.schemas import PostIdData

log = logging.getLogger(__name__)

_IDEMP_POST_CREATE_ADAPTER = TypeAdapter(ApiResponse[PostIdData])

_IDEMP_KEY_MIN = 8
_IDEMP_KEY_MAX = 128


def get_client_identifier(request: Request) -> str:
    """프록시 검증이 끝난 scope["client"]만 사용한다(신뢰 프록시 뒤에서는 ProxyHeadersMiddleware가
    이미 실제 IP로 갱신). 원시 X-Forwarded-For를 직접 읽으면 임의 위조가 가능해 조회수 dedup
    (viewer_key)을 요청마다 우회할 수 있다 — rate limit 키 산정과 동일 규약."""
    client = request.scope.get("client") or ("0.0.0.0", 0)
    return (client[0] or "0.0.0.0").strip()


def _normalize_idempotency_key(raw: str | None) -> str | None:
    if raw is None:
        return None
    s = raw.strip()
    if not s:
        return None
    if len(s) < _IDEMP_KEY_MIN or len(s) > _IDEMP_KEY_MAX:
        raise HTTPException(
            status_code=400,
            detail={
                "code": ApiCode.INVALID_REQUEST.value,
                "message": f"X-Idempotency-Key는 {_IDEMP_KEY_MIN}~{_IDEMP_KEY_MAX}자여야 합니다.",
                "data": None,
            },
        )
    return s


def _coerce_idempotency_key(raw: str | None) -> str | None:
    if raw is None:
        return None
    s = raw.strip()
    if not s or len(s) < _IDEMP_KEY_MIN or len(s) > _IDEMP_KEY_MAX:
        return None
    return s


def _idempotency_fingerprint(scope_parts: tuple[str, ...], norm: str) -> str:
    return hashlib.sha256(":".join((*scope_parts, norm)).encode()).hexdigest()


def _result_redis_key(namespace: str, fp: str) -> str:
    return f"idemp:{namespace}:res:{fp}"


def _lock_redis_key(namespace: str, fp: str) -> str:
    return f"idemp:{namespace}:lock:{fp}"


def _merge_request_id_into_cached_body(body: dict[str, Any], request: Request) -> dict[str, Any]:
    out = dict(body)
    out["requestId"] = get_request_id(request)
    return out


def _redis_client(request: Request) -> Any | None:
    redis_raw = getattr(request.app.state, "redis", None)
    if not isinstance(redis_raw, Redis):
        return None
    return redis_raw


async def idempotency_before(
    request: Request,
    raw_key: str | None,
    *,
    fingerprint_scope_parts: tuple[str, ...],
    namespace: str,
    lock_ttl_sec: int,
    conflict_message: str,
    success_status: int = 201,
    cache_adapter: TypeAdapter[Any],
) -> JSONResponse | None:
    try:
        norm = _normalize_idempotency_key(raw_key)
    except HTTPException:
        raise
    if norm is None:
        return None

    rcli = _redis_client(request)
    if rcli is None:
        return None

    fp = _idempotency_fingerprint(fingerprint_scope_parts, norm)
    res_key = _result_redis_key(namespace, fp)
    lock_key = _lock_redis_key(namespace, fp)

    try:
        cached = await rcli.get(res_key)
        if cached:
            payload: bytes | str
            if isinstance(cached, (bytes, bytearray)):
                payload = bytes(cached)
            else:
                payload = str(cached)
            try:
                validated = cache_adapter.validate_json(payload)
            except ValidationError as e:
                log.warning(
                    "멱등성 캐시 검증 실패(캐시 미스 처리) ns=%s fp_prefix=%s: %s",
                    namespace,
                    fp[:16],
                    e,
                )
            else:
                body = validated.model_dump(mode="json", by_alias=True)
                return JSONResponse(
                    status_code=success_status,
                    content=_merge_request_id_into_cached_body(body, request),
                )

        got_lock = await rcli.set(lock_key, "1", nx=True, ex=lock_ttl_sec)
        if not got_lock:
            raise HTTPException(
                status_code=409,
                detail={
                    "code": ApiCode.CONFLICT.value,
                    "message": conflict_message,
                    "data": None,
                },
            )
    except HTTPException:
        raise
    except Exception as e:
        log.warning("멱등성 Redis 오류(Fail-open) ns=%s: %s", namespace, e)
        return None

    return None


async def idempotency_after_success(
    request: Request,
    raw_key: str | None,
    *,
    fingerprint_scope_parts: tuple[str, ...],
    namespace: str,
    result_ttl_sec: int,
    response_obj: Any,
) -> None:
    norm = _coerce_idempotency_key(raw_key)
    if norm is None:
        return

    rcli = _redis_client(request)
    if rcli is None:
        return

    fp = _idempotency_fingerprint(fingerprint_scope_parts, norm)
    res_key = _result_redis_key(namespace, fp)
    lock_key = _lock_redis_key(namespace, fp)

    try:
        dumped = response_obj.model_dump(mode="json", by_alias=True)
        await rcli.set(
            res_key,
            json.dumps(dumped, ensure_ascii=False),
            ex=result_ttl_sec,
        )
    except Exception as e:
        log.warning("멱등성 성공 캐시 저장 실패 ns=%s: %s", namespace, e)
    try:
        await rcli.delete(lock_key)
    except Exception as e:
        log.warning("멱등성 잠금 해제 실패 ns=%s: %s", namespace, e)


async def idempotency_after_failure(
    request: Request,
    raw_key: str | None,
    *,
    fingerprint_scope_parts: tuple[str, ...],
    namespace: str,
) -> None:
    norm = _coerce_idempotency_key(raw_key)
    if norm is None:
        return

    rcli = _redis_client(request)
    if rcli is None:
        return

    fp = _idempotency_fingerprint(fingerprint_scope_parts, norm)
    try:
        await rcli.delete(_lock_redis_key(namespace, fp))
    except Exception as e:
        log.warning("멱등성 실패 시 잠금 해제 오류 ns=%s: %s", namespace, e)


# --- POST /posts ---


async def post_create_idempotency_before(
    request: Request, user_id: UUID, raw_key: str | None
) -> JSONResponse | None:
    return await idempotency_before(
        request,
        raw_key,
        fingerprint_scope_parts=(str(user_id),),
        namespace="post:create",
        lock_ttl_sec=settings.IDEMPOTENCY_POST_CREATE_LOCK_TTL_SECONDS,
        conflict_message="동일 멱등성 키로 게시글 생성이 진행 중입니다.",
        cache_adapter=_IDEMP_POST_CREATE_ADAPTER,
    )


async def post_create_idempotency_after_success(
    request: Request,
    user_id: UUID,
    raw_key: str | None,
    response_obj: Any,
) -> None:
    await idempotency_after_success(
        request,
        raw_key,
        fingerprint_scope_parts=(str(user_id),),
        namespace="post:create",
        result_ttl_sec=settings.IDEMPOTENCY_POST_CREATE_TTL_SECONDS,
        response_obj=response_obj,
    )


async def post_create_idempotency_after_failure(
    request: Request,
    user_id: UUID,
    raw_key: str | None,
) -> None:
    await idempotency_after_failure(
        request,
        raw_key,
        fingerprint_scope_parts=(str(user_id),),
        namespace="post:create",
    )
