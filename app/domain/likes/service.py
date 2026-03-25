# Likes 도메인 서비스. Full-Async. IntegrityError(23505) 시 AlreadyLikedException으로 변환.
# 하나의 요청당 하나의 async with db.begin()으로 묶어 Race Condition 방지.
from __future__ import annotations

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.exc import StaleDataError

from app.comments.model import CommentLikesModel, CommentsModel
from app.common.exceptions import (
    AlreadyLikedException,
    CommentNotFoundException,
    ConcurrentUpdateException,
    PostNotFoundException,
)
from app.db import get_connection
from app.domain.likes.model import PostLikesModel
from app.posts.model import PostsModel


def _is_unique_violation(exc: IntegrityError) -> bool:
    orig = getattr(exc, "orig", None)
    pgcode = getattr(orig, "pgcode", None) if orig else None
    return pgcode == "23505"


class LikeService:
    @classmethod
    async def is_post_liked(cls, post_id: int, user_id: int, db: AsyncSession) -> bool:
        return await PostLikesModel.has_like(post_id, user_id, db=db)

    @classmethod
    async def like_post(
        cls, post_id: int, user_id: int, db: AsyncSession
    ) -> tuple[bool, int, bool]:
        async with db.begin():
            if await PostsModel.get_post_by_id(post_id, db=db) is None:
                raise PostNotFoundException()
            try:
                inserted = await PostLikesModel.create(post_id, user_id, db=db)
                if inserted:
                    like_count = await PostsModel.increment_like_count(post_id, db=db)
                else:
                    like_count = await PostsModel.get_like_count(post_id, db=db)
                return (True, like_count, inserted)
            except IntegrityError as e:
                if _is_unique_violation(e):
                    async with get_connection() as db2:
                        async with db2.begin():
                            like_count = await PostsModel.get_like_count(post_id, db=db2)
                    raise AlreadyLikedException(
                        data={"likeCount": like_count, "isLiked": True},
                    ) from e
                raise
            except StaleDataError as e:
                raise ConcurrentUpdateException() from e

    @classmethod
    async def unlike_post(cls, post_id: int, user_id: int, db: AsyncSession) -> tuple[bool, int]:
        async with db.begin():
            if await PostsModel.get_post_by_id(post_id, db=db) is None:
                raise PostNotFoundException()
            try:
                deleted = await PostLikesModel.delete(post_id, user_id, db=db)
                if deleted:
                    like_count = await PostsModel.decrement_like_count(post_id, db=db)
                else:
                    like_count = await PostsModel.get_like_count(post_id, db=db)
            except StaleDataError as e:
                raise ConcurrentUpdateException() from e
        return (False, like_count)

    @classmethod
    async def like_comment(
        cls, comment_id: int, user_id: int, db: AsyncSession
    ) -> tuple[bool, int, bool]:
        async with db.begin():
            if await CommentsModel.get_comment_by_id(comment_id, db=db) is None:
                raise CommentNotFoundException()
            try:
                inserted = await CommentLikesModel.create(comment_id, user_id, db=db)
                if inserted:
                    like_count = await CommentLikesModel.increment_like_count(comment_id, db=db)
                else:
                    like_count = await CommentsModel.get_like_count(comment_id, db=db)
                return (True, like_count, inserted)
            except IntegrityError as e:
                if _is_unique_violation(e):
                    async with get_connection() as db2:
                        async with db2.begin():
                            like_count = await CommentsModel.get_like_count(comment_id, db=db2)
                    raise AlreadyLikedException(
                        data={"likeCount": like_count, "isLiked": True},
                    ) from e
                raise
            except StaleDataError as e:
                raise ConcurrentUpdateException() from e

    @classmethod
    async def unlike_comment(
        cls, comment_id: int, user_id: int, db: AsyncSession
    ) -> tuple[bool, int]:
        async with db.begin():
            if await CommentsModel.get_comment_by_id(comment_id, db=db) is None:
                raise CommentNotFoundException()
            try:
                deleted = await CommentLikesModel.delete(comment_id, user_id, db=db)
                if deleted:
                    like_count = await CommentLikesModel.decrement_like_count(comment_id, db=db)
                else:
                    like_count = await CommentsModel.get_like_count(comment_id, db=db)
            except StaleDataError as e:
                raise ConcurrentUpdateException() from e
        return (False, like_count)
