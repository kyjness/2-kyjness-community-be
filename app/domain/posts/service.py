# 게시글 비즈니스 로직. Full-Async.
# 조회수 중복 방지: Redis SET NX EX (멀티 워커). Redis 장애 시 Fail-open(매 요청 카운트).
from __future__ import annotations

import logging
import os
from typing import Any, List, Optional, Tuple

from sqlalchemy.ext.asyncio import AsyncSession

from app.common.exceptions import (
    InvalidImageException,
    PostNotFoundException,
    UserNotFoundException,
)
from app.media.model import MediaModel
from app.media.service import MediaService
from app.posts.model import PostsModel
from app.posts.schema import PostCreateRequest, PostResponse, PostUpdateRequest

log = logging.getLogger(__name__)

# 0이면 dedup 비활성(매 조회마다 DB 증가). 기본 1시간 윈도우.
_VIEW_REDIS_EX_SECONDS = max(0, int(os.getenv("VIEW_CACHE_TTL_SECONDS", "3600")))


def _view_redis_key(post_id: int, viewer_key: str) -> str:
    return f"view:post:{post_id}:viewer:{viewer_key}"


async def _consume_view_if_new_redis(
    post_id: int, viewer_key: str, redis_client: Any | None
) -> bool:
    """True면 이번 요청에서 DB 조회수를 올려도 됨. Redis 없음/오류 시 True(Fail-open)."""
    if _VIEW_REDIS_EX_SECONDS <= 0:
        return True
    if redis_client is None:
        return True
    key = _view_redis_key(post_id, viewer_key)
    try:
        created = await redis_client.set(
            key, "1", nx=True, ex=_VIEW_REDIS_EX_SECONDS
        )
        return bool(created)
    except Exception as e:
        log.warning("조회수 dedup Redis 오류(Fail-open, 증가 허용): %s", e)
        return True


class PostService:
    @classmethod
    async def create_post(
        cls,
        user_id: int,
        data: PostCreateRequest,
        db: AsyncSession,
    ) -> int:
        async with db.begin():
            if data.image_ids:
                images = await MediaModel.get_images_by_ids(data.image_ids, db=db)
                if set(i.id for i in images) != set(data.image_ids):
                    raise InvalidImageException()
            return await PostsModel.create_post(
                user_id, data.title, data.content, data.image_ids, db=db
            )

    @classmethod
    async def get_posts(
        cls,
        page: int,
        size: int,
        db: AsyncSession,
        q: Optional[str] = None,
        sort: Optional[str] = None,
        current_user_id: Optional[int] = None,
    ) -> Tuple[List[PostResponse], bool, int]:
        """통합 목록 API: q(검색어) ILIKE, sort: latest|popular|views|oldest."""
        search_q = q.strip() if (q and q.strip()) else None
        async with db.begin():
            posts, has_more = await PostsModel.get_all_posts(
                page,
                size,
                db=db,
                search_q=search_q,
                sort=sort,
                current_user_id=current_user_id,
            )
            total = await PostsModel.get_posts_count(
                db=db, search_q=search_q, current_user_id=current_user_id
            )
            result = [PostResponse.model_validate(p) for p in posts if p.user]
        return result, has_more, total

    @classmethod
    async def record_post_view(
        cls,
        post_id: int,
        viewer_key: str,
        db: AsyncSession,
        current_user_id: Optional[int] = None,
        redis_client: Any | None = None,
    ) -> None:
        async with db.begin():
            post = await PostsModel.get_post_by_id(
                post_id, db=db, current_user_id=current_user_id
            )
            if not post:
                raise PostNotFoundException()
            if not await _consume_view_if_new_redis(post_id, viewer_key, redis_client):
                return
            await PostsModel.increment_view_count(post_id, db=db)

    @classmethod
    async def get_post_detail(
        cls,
        post_id: int,
        db: AsyncSession,
        current_user_id: Optional[int] = None,
        *,
        viewer_key: str,
        redis_client: Any | None = None,
        writer_db: AsyncSession | None = None,
    ) -> PostResponse:
        async with db.begin():
            post = await PostsModel.get_post_by_id(
                post_id, db=db, current_user_id=current_user_id
            )
            if not post:
                raise PostNotFoundException()
            if not post.user:
                raise UserNotFoundException()
            data = PostResponse.model_validate(post)
            if current_user_id is not None:
                from app.domain.likes.service import LikeService

                is_liked = await LikeService.is_post_liked(post_id, current_user_id, db=db)
                data = data.model_copy(update={"is_liked": is_liked})

        if writer_db is not None and await _consume_view_if_new_redis(
            post_id, viewer_key, redis_client
        ):
            async with writer_db.begin():
                await PostsModel.increment_view_count(post_id, db=writer_db)
            data = data.model_copy(update={"view_count": data.view_count + 1})

        return data

    @classmethod
    async def update_post(
        cls,
        post_id: int,
        data: PostUpdateRequest,
        db: AsyncSession,
    ) -> None:
        async with db.begin():
            post = await PostsModel.get_post_by_id(post_id, db=db)
            if not post:
                raise PostNotFoundException()
            if data.image_ids is not None:
                images = await MediaModel.get_images_by_ids(data.image_ids, db=db)
                if set(i.id for i in images) != set(data.image_ids):
                    raise InvalidImageException()
            released = await PostsModel.update_post(
                post_id,
                title=data.title,
                content=data.content,
                image_ids=data.image_ids,
                db=db,
            )
            for iid in released or []:
                await MediaService.decrement_ref_count(iid, db=db)

    @classmethod
    async def delete_post(cls, post_id: int, db: AsyncSession) -> None:
        async with db.begin():
            success, image_ids = await PostsModel.delete_post(post_id, db=db)
            if not success:
                raise PostNotFoundException()
            for iid in image_ids:
                await MediaService.decrement_ref_count(iid, db=db)

    @classmethod
    async def search_posts(
        cls,
        page: int,
        size: int,
        db: AsyncSession,
        q: Optional[str] = None,
        sort: Optional[str] = None,
    ) -> Tuple[List[PostResponse], bool, int]:
        return await cls.get_posts(page=page, size=size, db=db, q=q, sort=sort)
