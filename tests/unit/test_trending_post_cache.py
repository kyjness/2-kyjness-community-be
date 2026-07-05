"""트렌딩 게시글 캐시(ADR 0004) 단위 테스트 — 외부 인프라 없이 캐시 wiring을 검증한다.

차단 무관 랭킹 풀을 캐시하고 차단은 요청별 오버레이한다는 설계의 핵심 불변식을 확인:
캐시 히트 시 DB 없이 limit만큼 슬라이스 · 차단 저자 사후 필터 · Redis 부재 시 loader 폴백.
"""

import asyncio
from typing import cast
from uuid import uuid4

from app.core import metrics
from app.domain.posts.repository import PostsModel
from app.domain.posts.services.trending_post_service import (
    _POOL_ADAPTER,
    TrendingPostService,
    _TrendingCacheItem,
)
from sqlalchemy.ext.asyncio import AsyncSession


def _hit(**labels) -> float:
    return metrics.CACHE_EVENTS.labels(**labels)._value.get()


class _HitRedis:
    """캐시 히트만 흉내내는 가짜. 히트 경로는 get 외 명령을 쓰지 않는다."""

    def __init__(self, payload: bytes) -> None:
        self._payload = payload

    async def get(self, key):
        return self._payload


class _FakeBegin:
    async def __aenter__(self):
        return None

    async def __aexit__(self, *a):
        return False


class _FakeDB:
    """차단 오버레이는 db.begin() 안에서 조회한다(세션 autobegin=False 재현). begin만 흉내낸다."""

    def begin(self):
        return _FakeBegin()


def _pool(*items: _TrendingCacheItem) -> bytes:
    return _POOL_ADAPTER.dump_json(list(items))


def test_cache_hit_slices_to_limit_without_db():
    items = [_TrendingCacheItem(id=uuid4(), title=f"t{i}", author_id=uuid4()) for i in range(30)]
    redis = _HitRedis(_pool(*items))

    before = _hit(cache="trending_posts", result="hit")
    # 히트 경로는 loader(DB)를 태우지 않으므로 db=None을 cast로 전달, current_user_id 없음.
    result = asyncio.run(
        TrendingPostService.get_trending_posts(
            db=cast(AsyncSession, None), redis_client=redis, limit=5
        )
    )
    assert len(result) == 5  # 풀(30)에서 limit만큼만
    assert result[0].title == "t0"
    assert _hit(cache="trending_posts", result="hit") - before == 1


def test_block_overlay_filters_blocked_authors(monkeypatch):
    blocked = uuid4()
    items = (
        _TrendingCacheItem(id=uuid4(), title="차단글", author_id=blocked),
        _TrendingCacheItem(id=uuid4(), title="정상글", author_id=uuid4()),
    )
    redis = _HitRedis(_pool(*items))

    async def _fake_blocked(cls, blocker_id, *, db):
        return {blocked}

    monkeypatch.setattr(PostsModel, "get_blocked_author_ids", classmethod(_fake_blocked))

    result = asyncio.run(
        TrendingPostService.get_trending_posts(
            db=cast(AsyncSession, _FakeDB()),
            redis_client=redis,
            limit=10,
            current_user_id=uuid4(),
        )
    )
    titles = [r.title for r in result]
    assert titles == ["정상글"]  # 차단 저자 글은 사후 필터로 제거


def test_redis_none_uses_loader(monkeypatch):
    items = [_TrendingCacheItem(id=uuid4(), title="폴백", author_id=None)]

    async def _fake_pool(cls, *, db, window_hours, category_id):
        return items

    monkeypatch.setattr(TrendingPostService, "_compute_pool", classmethod(_fake_pool))

    result = asyncio.run(
        TrendingPostService.get_trending_posts(
            db=cast(AsyncSession, None), redis_client=None, limit=10
        )
    )
    assert [r.title for r in result] == ["폴백"]
