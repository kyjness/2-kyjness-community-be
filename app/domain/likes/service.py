# Likes 도메인 서비스. Full-Async. IntegrityError(23505) 시 AlreadyLikedException으로 변환.
# 하나의 요청당 하나의 async with db.begin()으로 묶어 Race Condition 방지.
from __future__ import annotations

from redis.asyncio import Redis
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.exc import StaleDataError

from app.comments.model import CommentLikesModel, CommentsModel
from app.common.enums import NotificationKind
from app.common.exceptions import (
    AlreadyLikedException,
    CommentNotFoundException,
    ConcurrentUpdateException,
    PostNotFoundException,
)
from app.db import get_connection
from app.likes.model import PostLikesModel
from app.notifications.model import NotificationsModel
from app.notifications.service import NotificationService
from app.posts.repository import PostsModel


def _is_unique_violation(exc: IntegrityError) -> bool:
    orig = getattr(exc, "orig", None)
    pgcode = getattr(orig, "pgcode", None) if orig else None
    return pgcode == "23505"


class LikeService:
    @classmethod
    async def is_post_liked(cls, post_id: str, user_id: str, db: AsyncSession) -> bool:
        return await PostLikesModel.has_like(post_id, user_id, db=db)

    @classmethod
    async def like_post(
        cls,
        post_id: str,
        user_id: str,
        db: AsyncSession,
        redis: Redis | None = None,
    ) -> tuple[bool, int, bool]:
        notify: tuple[str, str, NotificationKind, str | None, str | None, str | None] | None = None
        inserted_out = False
        like_count_out = 0
        async with db.begin():
            if await PostsModel.get_post_by_id(post_id, db=db) is None:
                raise PostNotFoundException()
            try:
                inserted = await PostLikesModel.create(post_id, user_id, db=db)
                if inserted:
                    like_count = await PostsModel.increment_like_count(post_id, db=db)
                    author_id = await PostsModel.get_post_author_id(post_id, db=db)
                    if author_id and author_id != user_id:
                        nid = await NotificationsModel.insert(
                            user_id=author_id,
                            kind=NotificationKind.LIKE_POST,
                            actor_id=user_id,
                            post_id=post_id,
                            comment_id=None,
                            db=db,
                        )
                        notify = (
                            author_id,
                            nid,
                            NotificationKind.LIKE_POST,
                            user_id,
                            post_id,
                            None,
                        )
                else:
                    like_count = await PostsModel.get_like_count(post_id, db=db)
                inserted_out = inserted
                like_count_out = like_count
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
        if notify is not None:
            rec, nid, kind, act, pid, cid = notify
            await NotificationService.publish_after_commit(
                redis,
                recipient_user_id=rec,
                notification_id=nid,
                kind=kind,
                actor_id=act,
                post_id=pid,
                comment_id=cid,
            )
        return (True, like_count_out, inserted_out)

    @classmethod
    async def unlike_post(cls, post_id: str, user_id: str, db: AsyncSession) -> tuple[bool, int]:
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
        cls,
        comment_id: str,
        user_id: str,
        db: AsyncSession,
        redis: Redis | None = None,
    ) -> tuple[bool, int, bool]:
        notify: tuple[str, str, NotificationKind, str | None, str | None, str | None] | None = None
        inserted_out = False
        like_count_out = 0
        async with db.begin():
            comment_row = await CommentsModel.get_comment_by_id(comment_id, db=db)
            if comment_row is None:
                raise CommentNotFoundException()
            try:
                inserted = await CommentLikesModel.create(comment_id, user_id, db=db)
                if inserted:
                    like_count = await CommentLikesModel.increment_like_count(comment_id, db=db)
                    author_id = comment_row.author_id
                    if author_id and author_id != user_id:
                        nid = await NotificationsModel.insert(
                            user_id=author_id,
                            kind=NotificationKind.LIKE_COMMENT,
                            actor_id=user_id,
                            post_id=comment_row.post_id,
                            comment_id=comment_id,
                            db=db,
                        )
                        notify = (
                            author_id,
                            nid,
                            NotificationKind.LIKE_COMMENT,
                            user_id,
                            comment_row.post_id,
                            comment_id,
                        )
                else:
                    like_count = await CommentsModel.get_like_count(comment_id, db=db)
                inserted_out = inserted
                like_count_out = like_count
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
        if notify is not None:
            rec, nid, kind, act, pid, cid = notify
            await NotificationService.publish_after_commit(
                redis,
                recipient_user_id=rec,
                notification_id=nid,
                kind=kind,
                actor_id=act,
                post_id=pid,
                comment_id=cid,
            )
        return (True, like_count_out, inserted_out)

    @classmethod
    async def unlike_comment(
        cls, comment_id: str, user_id: str, db: AsyncSession
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
