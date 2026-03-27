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
    InvalidRequestException,
    PostNotFoundException,
)
from app.media.model import MediaModel
from app.posts.model import PostsModel
from app.posts.schema import PostCreateRequest, PostResponse, PostUpdateRequest

log = logging.getLogger(__name__)

# viewer·post당 TTL 초 동안 1회만 조회수 증가(SET NX EX).
# 개발/로컬에서 새로고침·중복 호출로 조회수가 튀는 문제가 잦아 기본값은 1시간으로 둔다.
#
# NOTE: 과거 설정에서 VIEW_CACHE_TTL_SECONDS=0(비활성)로 남아 있는 경우가 있어,
#       0 이하 값은 안전하게 기본값(3600)으로 보정한다.
_raw_view_ttl = os.getenv("VIEW_CACHE_TTL_SECONDS")
try:
    _parsed_view_ttl = int(_raw_view_ttl) if _raw_view_ttl is not None else 3600
except ValueError:
    _parsed_view_ttl = 3600
_VIEW_REDIS_EX_SECONDS = _parsed_view_ttl if _parsed_view_ttl > 0 else 3600

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


def _view_redis_key(post_id: str, viewer_key: str) -> str:
    return f"view:post:{post_id}:viewer:{viewer_key}"


async def _consume_view_if_new_redis(
    post_id: str, viewer_key: str, redis_client: Any | None
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
        user_id: str,
        data: PostCreateRequest,
        db: AsyncSession,
    ) -> int:
        async with db.begin():
            if data.category_id is not None:
                ok = await PostsModel.category_exists(data.category_id, db=db)
                if not ok:
                    raise InvalidRequestException("존재하지 않는 카테고리입니다.")
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
        category_id: int | None = None,
        current_user_id: str | None = None,
    ) -> tuple[list[PostResponse], bool, int]:
        search_q = q.strip() if (q and q.strip()) else None
        async with db.begin():
            if category_id is not None:
                ok = await PostsModel.category_exists(category_id, db=db)
                if not ok:
                    raise InvalidRequestException("존재하지 않는 카테고리입니다.")
            posts, has_more = await PostsModel.get_all_posts(
                page,
                size,
                db=db,
                search_q=search_q,
                sort=sort,
                category_id=category_id,
                current_user_id=current_user_id,
            )
            total = await PostsModel.get_posts_count(
                db=db,
                search_q=search_q,
                category_id=category_id,
                current_user_id=current_user_id,
            )
            # 유저가 하드 삭제되면 posts.user_id가 NULL이 될 수 있으므로, 게시글은 보존하고 author만 None 처리.
            result = [PostResponse.model_validate(p) for p in posts]
        return result, has_more, total

    @classmethod
    async def record_post_view(
        cls,
        post_id: str,
        viewer_key: str,
        db: AsyncSession,
        current_user_id: str | None = None,
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
        post_id: str,
        db: AsyncSession,
        current_user_id: str | None = None,
        *,
        viewer_key: str,
        redis_client: Any | None = None,
        writer_db: AsyncSession | None = None,
    ) -> PostResponse:
        async with db.begin():
            if current_user_id is not None:
                post_with_like = await PostsModel.get_post_by_id_with_like_flag(
                    post_id, current_user_id, db=db
                )
                if not post_with_like:
                    raise PostNotFoundException()
                post, is_liked = post_with_like
                data = PostResponse.model_validate(post).model_copy(update={"is_liked": is_liked})
            else:
                post = await PostsModel.get_post_by_id(post_id, db=db, current_user_id=None)
                if not post:
                    raise PostNotFoundException()
                data = PostResponse.model_validate(post)

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
        post_id: str,
        data: PostUpdateRequest,
        db: AsyncSession,
    ) -> None:
        fs = data.model_fields_set
        async with db.begin():
            post = await PostsModel.get_post_by_id(post_id, db=db)
            if not post:
                raise PostNotFoundException()
            if "version" in fs and data.version is not None:
                if data.version != post.version:
                    raise ConcurrentUpdateException(
                        "다른 사용자가 이미 글을 수정했습니다. 최신 데이터를 확인해주세요."
                    )
            title = data.title if "title" in fs else None
            content = data.content if "content" in fs else None
            image_ids = data.image_ids if "image_ids" in fs else None
            category_id = data.category_id if "category_id" in fs else None
            hashtags_raw = data.hashtags if "hashtags" in fs else None
            if category_id is not None:
                ok = await PostsModel.category_exists(category_id, db=db)
                if not ok:
                    raise InvalidRequestException("존재하지 않는 카테고리입니다.")
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
    async def delete_post(cls, post_id: str, db: AsyncSession) -> None:
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
