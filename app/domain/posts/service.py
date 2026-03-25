# 게시글 비즈니스 로직. Full-Async.
# 조회수 중복 방지: Redis SET NX EX (멀티 워커). Redis 장애 시 Fail-open(매 요청 카운트).
from __future__ import annotations

import logging
import os
import re
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.exc import StaleDataError

from app.common.exceptions import (
    ConcurrentUpdateException,
    InvalidImageException,
    PostNotFoundException,
    UserNotFoundException,
)
from app.media.model import MediaModel
from app.posts.model import PostsModel
from app.posts.schema import PostCreateRequest, PostResponse, PostUpdateRequest

log = logging.getLogger(__name__)

# 0이면 dedup 비활성. >0이면 viewer·post당 TTL 초 동안 1회만(환경변수로 조정).
_VIEW_REDIS_EX_SECONDS = max(0, int(os.getenv("VIEW_CACHE_TTL_SECONDS", "0")))

_HASHTAG_ALLOWED_RE = re.compile(r"[^0-9a-z가-힣_]")


def _normalize_hashtags(raw: list[str]) -> list[str]:
    """해시태그 정규화.

    - 앞/뒤 공백 제거
    - 선행 '#' 제거
    - 소문자 변환
    - 공백/특수문자 제거(허용: 한글/영문/숫자/언더스코어)
    - 중복 제거(입력 순서 유지)
    """
    seen: set[str] = set()
    out: list[str] = []
    for v in raw:
        s = (v or "").strip()
        if not s:
            continue
        if s.startswith("#"):
            s = s[1:].strip()
        s = s.lower()
        s = "".join(s.split())
        s = _HASHTAG_ALLOWED_RE.sub("", s)
        if not s:
            continue
        if len(s) > 50:
            s = s[:50]
        if s in seen:
            continue
        seen.add(s)
        out.append(s)
    return out


def _view_redis_key(post_id: int, viewer_key: str) -> str:
    return f"view:post:{post_id}:viewer:{viewer_key}"


async def _consume_view_if_new_redis(
    post_id: int, viewer_key: str, redis_client: Any | None
) -> bool:
    if _VIEW_REDIS_EX_SECONDS <= 0:
        return True
    if redis_client is None:
        return True
    key = _view_redis_key(post_id, viewer_key)
    try:
        created = await redis_client.set(key, "1", nx=True, ex=_VIEW_REDIS_EX_SECONDS)
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
            hashtags = _normalize_hashtags(data.hashtags) if data.hashtags is not None else None
            post_id = await PostsModel.create_post(
                user_id,
                data.title,
                data.content,
                data.image_ids,
                category_id=data.category_id,
                hashtag_names=hashtags,
                db=db,
            )
            return post_id

    @classmethod
    async def get_posts(
        cls,
        page: int,
        size: int,
        db: AsyncSession,
        q: str | None = None,
        sort: str | None = None,
        current_user_id: int | None = None,
    ) -> tuple[list[PostResponse], bool, int]:
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
        current_user_id: int | None = None,
        redis_client: Any | None = None,
    ) -> None:
        async with db.begin():
            post = await PostsModel.get_post_by_id(post_id, db=db, current_user_id=current_user_id)
            if not post:
                raise PostNotFoundException()
            if not await _consume_view_if_new_redis(post_id, viewer_key, redis_client):
                return
            try:
                await PostsModel.increment_view_count(post_id, db=db)
            except StaleDataError as e:
                raise ConcurrentUpdateException() from e

    @classmethod
    async def get_post_detail(
        cls,
        post_id: int,
        db: AsyncSession,
        current_user_id: int | None = None,
        *,
        viewer_key: str,
        redis_client: Any | None = None,
        writer_db: AsyncSession | None = None,
    ) -> PostResponse:
        async with db.begin():
            post = await PostsModel.get_post_by_id(post_id, db=db, current_user_id=current_user_id)
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
                try:
                    await PostsModel.increment_view_count(post_id, db=writer_db)
                except StaleDataError as e:
                    raise ConcurrentUpdateException() from e
            data = data.model_copy(update={"view_count": data.view_count + 1})

        return data

    @classmethod
    async def update_post(
        cls,
        post_id: int,
        data: PostUpdateRequest,
        db: AsyncSession,
    ) -> None:
        fs = data.model_fields_set
        async with db.begin():
            post = await PostsModel.get_post_by_id(post_id, db=db)
            if not post:
                raise PostNotFoundException()
            title = data.title if "title" in fs else None
            content = data.content if "content" in fs else None
            image_ids = data.image_ids if "image_ids" in fs else None
            category_id = data.category_id if "category_id" in fs else None
            hashtags_raw = data.hashtags if "hashtags" in fs else None
            if image_ids is not None:
                images = await MediaModel.get_images_by_ids(image_ids, db=db)
                if set(i.id for i in images) != set(image_ids):
                    raise InvalidImageException()
            hashtags = _normalize_hashtags(hashtags_raw) if hashtags_raw is not None else None
            try:
                delta = await PostsModel.update_post(
                    post_id,
                    title=title,
                    content=content,
                    image_ids=image_ids,
                    category_id=category_id,
                    hashtag_names=hashtags,
                    db=db,
                )
            except StaleDataError as e:
                raise ConcurrentUpdateException() from e

            if delta is None:
                raise PostNotFoundException()

    @classmethod
    async def delete_post(cls, post_id: int, db: AsyncSession) -> None:
        async with db.begin():
            success, _image_ids = await PostsModel.delete_post(post_id, db=db)
            if not success:
                raise PostNotFoundException()

    @classmethod
    async def search_posts(
        cls,
        page: int,
        size: int,
        db: AsyncSession,
        q: str | None = None,
        sort: str | None = None,
    ) -> tuple[list[PostResponse], bool, int]:
        return await cls.get_posts(page=page, size=size, db=db, q=q, sort=sort)
