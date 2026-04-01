from __future__ import annotations

import asyncio
import logging
import os
from typing import Any

from pydantic import TypeAdapter, ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from app.posts.schemas import TrendingHashtagResponse

from ..repository import PostsModel

log = logging.getLogger(__name__)

_TRENDING_LIST_ADAPTER = TypeAdapter(list[TrendingHashtagResponse])


class HashtagService:
    CACHE_TRENDING_HASHTAGS_KEY = "cache:trending_hashtags"
    _TRENDING_HASHTAGS_TTL_SECONDS = 600
    _TRENDING_HASHTAGS_LOCK_KEY = "cache:trending_hashtags:lock"
    _TRENDING_HASHTAGS_LOCK_TTL_SECONDS = 5
    _TRENDING_HASHTAGS_WAIT_MAX_SECONDS = 2.0
    _TRENDING_HASHTAGS_WAIT_INTERVAL_SECONDS = 0.1

    @classmethod
    async def get_trending_hashtags(
        cls,
        *,
        db: AsyncSession,
        redis_client: Any | None = None,
        limit: int = 10,
    ) -> list[TrendingHashtagResponse]:
        def _decode_cached(v: Any) -> list[TrendingHashtagResponse] | None:
            if not v:
                return None
            raw: str | bytes = (
                v.decode("utf-8") if isinstance(v, (bytes, bytearray)) else str(v)
            )
            try:
                return _TRENDING_LIST_ADAPTER.validate_json(raw)
            except ValidationError as e:
                log.warning("trending_hashtags cache schema mismatch (ignore): %s", e)
                return None

        if redis_client is None:
            async with db.begin():
                rows = await PostsModel.get_trending_hashtags(db=db, limit=limit)
            return [TrendingHashtagResponse(name=name, count=count) for name, count in rows]

        try:
            cached = await redis_client.get(cls.CACHE_TRENDING_HASHTAGS_KEY)
            decoded = _decode_cached(cached)
            if decoded is not None:
                return decoded
        except Exception as e:
            log.warning("trending_hashtags redis cache read failed (fallback to DB): %s", e)
            async with db.begin():
                rows = await PostsModel.get_trending_hashtags(db=db, limit=limit)
            return [TrendingHashtagResponse(name=name, count=count) for name, count in rows]

        lock_value = os.urandom(16).hex()
        try:
            acquired = bool(
                await redis_client.set(
                    cls._TRENDING_HASHTAGS_LOCK_KEY,
                    lock_value,
                    nx=True,
                    ex=cls._TRENDING_HASHTAGS_LOCK_TTL_SECONDS,
                )
            )
        except Exception as e:
            log.warning("trending_hashtags redis lock failed (fallback to DB): %s", e)
            async with db.begin():
                rows = await PostsModel.get_trending_hashtags(db=db, limit=limit)
            return [TrendingHashtagResponse(name=name, count=count) for name, count in rows]

        if not acquired:
            waited = 0.0
            while waited < cls._TRENDING_HASHTAGS_WAIT_MAX_SECONDS:
                await asyncio.sleep(cls._TRENDING_HASHTAGS_WAIT_INTERVAL_SECONDS)
                waited += cls._TRENDING_HASHTAGS_WAIT_INTERVAL_SECONDS
                try:
                    cached2 = await redis_client.get(cls.CACHE_TRENDING_HASHTAGS_KEY)
                    decoded2 = _decode_cached(cached2)
                    if decoded2 is not None:
                        return decoded2
                except Exception:
                    break
            return []

        try:
            async with db.begin():
                rows = await PostsModel.get_trending_hashtags(db=db, limit=limit)
            result = [TrendingHashtagResponse(name=name, count=count) for name, count in rows]
            try:
                payload = _TRENDING_LIST_ADAPTER.dump_json(result).decode("utf-8")
                await redis_client.setex(
                    cls.CACHE_TRENDING_HASHTAGS_KEY, cls._TRENDING_HASHTAGS_TTL_SECONDS, payload
                )
            except Exception as e:
                log.warning("trending_hashtags redis cache write failed (ignore): %s", e)
            return result
        finally:
            try:
                await redis_client.eval(
                    "if redis.call('GET', KEYS[1]) == ARGV[1] then "
                    "return redis.call('DEL', KEYS[1]) else return 0 end",
                    1,
                    cls._TRENDING_HASHTAGS_LOCK_KEY,
                    lock_value,
                )
            except Exception:
                pass

