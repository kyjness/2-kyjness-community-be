# 게시글 비즈니스 로직. Full-Async.
# 조회수 중복 방지: 현재는 로컬 인메모리 캐시(용량 제한 + TTL) 사용.
# 향후 Redis의 SET NX EX로 즉시 전환 가능한 구조로 유지.
from __future__ import annotations

import os
import threading
import time
from typing import List, Optional, Tuple

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

VIEW_TTL_SECONDS = int(os.getenv("VIEW_CACHE_TTL_SECONDS", str(24 * 3600)))
VIEW_CACHE_MAX_SIZE = 50_000
_view_cache: dict[str, float] = {}
_view_cache_lock = threading.Lock()


def _view_cache_key(post_id: int, identifier: str) -> str:
    return f"view:post:{post_id}:ip:{identifier}"


def _evict_view_cache_if_needed() -> None:
    now = time.time()
    expired = [k for k, v in _view_cache.items() if v <= now]
    for k in expired:
        del _view_cache[k]
    if len(_view_cache) >= VIEW_CACHE_MAX_SIZE:
        ordered = list(_view_cache.keys())
        for k in ordered[: VIEW_CACHE_MAX_SIZE // 2]:
            _view_cache.pop(k, None)


def _consume_view_if_new(post_id: int, identifier: str) -> bool:
    if VIEW_TTL_SECONDS <= 0:
        return True
    key = _view_cache_key(post_id, identifier)
    now = time.time()
    expiry = now + VIEW_TTL_SECONDS
    with _view_cache_lock:
        if key in _view_cache and _view_cache[key] > now:
            return False
        _evict_view_cache_if_needed()
        _view_cache[key] = expiry
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
        client_identifier: str,
        db: AsyncSession,
        current_user_id: Optional[int] = None,
    ) -> None:
        async with db.begin():
            post = await PostsModel.get_post_by_id(
                post_id, db=db, current_user_id=current_user_id
            )
            if not post:
                raise PostNotFoundException()
            if not _consume_view_if_new(post_id, client_identifier):
                return
            await PostsModel.increment_view_count(post_id, db=db)

    @classmethod
    async def get_post_detail(
        cls,
        post_id: int,
        db: AsyncSession,
        current_user_id: Optional[int] = None,
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
