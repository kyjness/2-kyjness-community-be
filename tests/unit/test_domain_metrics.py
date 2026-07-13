"""도메인 메트릭(ADR 0006) — 외부 인프라 없이 계측 wiring을 검증한다.

rate limit 429·캐시 hit은 실제 코드 경로를 태워 카운터 증가를 확인하고, 세 패밀리가 /metrics
노출 대상(default registry)에 등록됐는지 확인한다. view-flush 카운터는 test_view_counter의 flush
테스트에서 델타 합으로 검증한다.
"""

import asyncio
from typing import cast

from app.core import metrics
from app.core.middleware.rate_limit import RateLimitMiddleware
from app.domain.posts.schemas import TrendingHashtagResponse
from app.domain.posts.services.hashtag_service import (
    _TRENDING_LIST_ADAPTER,
    HashtagService,
)
from prometheus_client import generate_latest
from sqlalchemy.ext.asyncio import AsyncSession


def _counter(counter, **labels) -> float:
    return counter.labels(**labels)._value.get()


def test_domain_metric_families_are_registered():
    body = generate_latest().decode("utf-8")
    assert "rate_limit_rejections_total" in body
    assert "cache_events_total" in body
    assert "view_buffer_flushed_views_total" in body


def test_cache_hit_increments_counter():
    # 캐시에 유효 payload가 있으면 hit로 집계하고 조기 반환한다(db 불필요).
    payload = _TRENDING_LIST_ADAPTER.dump_json([TrendingHashtagResponse(name="dog", count=3)])

    class _HitRedis:
        async def get(self, key):
            return payload

    before = _counter(metrics.CACHE_EVENTS, cache="trending_hashtags", result="hit")
    # hit 경로는 db를 건드리지 않고 조기 반환하므로 None을 cast로 전달.
    result = asyncio.run(
        HashtagService.get_trending_hashtags(
            db=cast(AsyncSession, None), redis_client=_HitRedis(), limit=10
        )
    )
    assert result[0].name == "dog"
    after = _counter(metrics.CACHE_EVENTS, cache="trending_hashtags", result="hit")
    assert after - before == 1


def test_rate_limit_rejection_increments_counter(monkeypatch):
    # redis 미연결 + critical path(login)는 메모리 리미터로 폴백 → 한도 초과 시 429.
    # 한도를 명시해 순서 의존 제거 — 통합 conftest가 세션 스코프로 한도를 완화하므로
    # 풀 스위트(integration→unit)에서는 기본값 전제가 깨진다.
    from app.core.config import settings

    monkeypatch.setattr(settings, "LOGIN_RATE_LIMIT_MAX_ATTEMPTS", 5)

    async def _dummy_app(scope, receive, send):
        await send({"type": "http.response.start", "status": 200, "headers": []})
        await send({"type": "http.response.body", "body": b""})

    mw = RateLimitMiddleware(_dummy_app)
    ip = "203.0.113.77"  # 테스트 전용 IP(다른 테스트와 키 충돌 방지)

    def _one_login() -> int:
        scope = {
            "type": "http",
            "path": "/v1/auth/login",
            "method": "POST",
            "headers": [],
            "client": (ip, 12345),
        }
        sent: list[dict] = []

        async def send(msg):
            sent.append(msg)

        async def receive():
            return {"type": "http.request", "body": b"", "more_body": False}

        asyncio.run(mw(scope, receive, send))
        return next(m["status"] for m in sent if m["type"] == "http.response.start")

    before = _counter(metrics.RATE_LIMIT_REJECTIONS, limit="login")
    statuses = [_one_login() for _ in range(20)]
    assert 429 in statuses  # 기본 한도(5회/창) 초과분은 429
    after = _counter(metrics.RATE_LIMIT_REJECTIONS, limit="login")
    assert after > before
