# Likes 도메인 모델. 게시글 좋아요(PostLike) 테이블 및 CRUD. AsyncSession.
# comment_likes·CommentLikesModel은 comments 도메인에 유지(순환 참조 방지).
from __future__ import annotations

from sqlalchemy import select, delete
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import mapped_column
from sqlalchemy import Integer, DateTime, ForeignKey

from app.db import Base, utc_now


class PostLike(Base):
    __tablename__ = "post_likes"

    post_id = mapped_column(
        Integer, ForeignKey("posts.id", ondelete="CASCADE"), primary_key=True
    )
    user_id = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    created_at = mapped_column(DateTime(timezone=True), nullable=False)


class PostLikesModel:
    @classmethod
    async def has_like(cls, post_id: int, user_id: int, db: AsyncSession) -> bool:
        result = await db.execute(
            select(1)
            .where(PostLike.post_id == post_id, PostLike.user_id == user_id)
            .limit(1)
        )
        return result.scalar_one_or_none() is not None

    @classmethod
    async def create(cls, post_id: int, user_id: int, *, db: AsyncSession) -> bool:
        stmt = (
            pg_insert(PostLike)
            .values(post_id=post_id, user_id=user_id, created_at=utc_now())
            .on_conflict_do_nothing(index_elements=[PostLike.post_id, PostLike.user_id])
            .returning(PostLike.post_id)
        )
        result = await db.execute(stmt)
        return result.scalar_one_or_none() is not None

    @classmethod
    async def delete(cls, post_id: int, user_id: int, db: AsyncSession) -> bool:
        r = await db.execute(
            delete(PostLike).where(
                PostLike.post_id == post_id, PostLike.user_id == user_id
            )
        )
        return r.rowcount > 0

    @classmethod
    async def delete_by_post_id(cls, post_id: int, db: AsyncSession) -> int:
        r = await db.execute(delete(PostLike).where(PostLike.post_id == post_id))
        return r.rowcount or 0
