from __future__ import annotations

import logging
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.posts.repository import PostsModel
from app.domain.posts.schemas import TrendingPostResponse

log = logging.getLogger(__name__)

# 24h time-decay 결과가 이보다 적으면 7일·좋아요순 fallback (데이터 부족 완화).
_MIN_POSTS_FOR_TIME_DECAY = 3
_FALLBACK_WINDOW_HOURS = 24 * 7


class TrendingPostService:
    # TODO(redis): cache:trending_posts:{window_hours}:{category_id|all} — TTL 300s, TypeAdapter + 분산 락
    # (HashtagService.get_trending_hashtags 패턴). redis_client 미지정 시 DB 직조회.

    @classmethod
    async def get_trending_posts(
        cls,
        *,
        db: AsyncSession,
        redis_client: Any | None = None,
        limit: int = 10,
        window_hours: int = 24,
        category_id: int | None = None,
        current_user_id: UUID | None = None,
    ) -> list[TrendingPostResponse]:
        _ = redis_client  # placeholder until Redis layer is wired

        async with db.begin():
            posts = await PostsModel.get_trending_posts(
                db=db,
                limit=limit,
                window_hours=window_hours,
                category_id=category_id,
                current_user_id=current_user_id,
                use_time_decay=True,
            )
            if len(posts) < _MIN_POSTS_FOR_TIME_DECAY:
                log.debug(
                    "trending_posts sparse in %sh window (%s rows); fallback to %sh like-order",
                    window_hours,
                    len(posts),
                    _FALLBACK_WINDOW_HOURS,
                )
                posts = await PostsModel.get_trending_posts(
                    db=db,
                    limit=limit,
                    window_hours=_FALLBACK_WINDOW_HOURS,
                    category_id=category_id,
                    current_user_id=current_user_id,
                    use_time_decay=False,
                )
            if len(posts) == 0:
                log.debug("trending_posts still empty; fallback to all-time like-order")
                posts = await PostsModel.get_trending_posts(
                    db=db,
                    limit=limit,
                    window_hours=None,
                    category_id=category_id,
                    current_user_id=current_user_id,
                    use_time_decay=False,
                )

        return [TrendingPostResponse.model_validate(p) for p in posts]
