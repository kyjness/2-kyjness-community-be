# 댓글 CRUD. Comment ORM 반환, Controller/매퍼에서 Schema로 직렬화. AsyncSession.
from typing import List, Optional, Set

from sqlalchemy import or_, select, update, delete, func
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import mapped_column, relationship, joinedload
from sqlalchemy import Integer, Text, DateTime, ForeignKey

from app.db import Base, utc_now
from app.users.model import User, DogProfile


class Comment(Base):
    __tablename__ = "comments"

    id = mapped_column(Integer, primary_key=True, autoincrement=True)
    post_id = mapped_column(
        Integer, ForeignKey("posts.id", ondelete="CASCADE"), nullable=False
    )
    author_id = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    parent_id = mapped_column(
        Integer, ForeignKey("comments.id", ondelete="CASCADE"), nullable=True
    )
    content = mapped_column(Text, nullable=False)
    like_count = mapped_column(Integer, default=0, nullable=False)
    created_at = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at = mapped_column(DateTime(timezone=True), nullable=False)
    deleted_at = mapped_column(DateTime(timezone=True), nullable=True)

    author = relationship(User, foreign_keys=[author_id])
    parent = relationship(
        "Comment",
        remote_side="Comment.id",
        back_populates="replies",
        foreign_keys=[parent_id],
    )
    replies = relationship("Comment", back_populates="parent", foreign_keys=[parent_id])
    likes = relationship(
        "CommentLike", back_populates="comment", foreign_keys="CommentLike.comment_id"
    )


class CommentLike(Base):
    __tablename__ = "comment_likes"

    comment_id = mapped_column(
        Integer, ForeignKey("comments.id", ondelete="CASCADE"), primary_key=True
    )
    user_id = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    created_at = mapped_column(DateTime(timezone=True), nullable=False)

    comment = relationship(Comment, back_populates="likes")
    user = relationship(User, foreign_keys=[user_id])


class CommentsModel:
    @classmethod
    async def create_comment(
        cls,
        post_id: int,
        user_id: int,
        content: str,
        db: AsyncSession,
        parent_id: Optional[int] = None,
    ) -> Comment:
        now = utc_now()
        c = Comment(
            post_id=post_id,
            author_id=user_id,
            parent_id=parent_id,
            content=content,
            like_count=0,
            created_at=now,
            updated_at=now,
            deleted_at=None,
        )
        db.add(c)
        await db.flush()
        return c

    @classmethod
    async def get_comment_by_id(
        cls, comment_id: int, db: AsyncSession, include_deleted: bool = False
    ) -> Optional[Comment]:
        stmt = (
            select(Comment)
            .where(Comment.id == comment_id)
            .options(
                joinedload(Comment.author).joinedload(User.profile_image),
                joinedload(Comment.author)
                .selectinload(User.dogs)
                .joinedload(DogProfile.profile_image),
            )
        )
        if not include_deleted:
            stmt = stmt.where(Comment.deleted_at.is_(None))
        result = await db.execute(stmt)
        return result.unique().scalars().one_or_none()

    @classmethod
    async def get_comments_by_post_id(
        cls,
        post_id: int,
        page: int = 1,
        size: int = 10,
        *,
        db: AsyncSession,
        fetch_all_for_tree: bool = False,
    ) -> List[Comment]:
        """fetch_all_for_tree=True: no pagination, return all for post (cap 500) to build tree.
        루트 댓글은 삭제된 것도 포함(프론트에서 '삭제된 댓글입니다' 표시).
        대댓글은 삭제된 것은 제외(deleted_at IS NULL인 것만)."""
        stmt = (
            select(Comment)
            .where(
                Comment.post_id == post_id,
                or_(Comment.deleted_at.is_(None), Comment.parent_id.is_(None)),
            )
            .options(
                joinedload(Comment.author).joinedload(User.profile_image),
                joinedload(Comment.author)
                .selectinload(User.dogs)
                .joinedload(DogProfile.profile_image),
            )
            .order_by(Comment.parent_id.asc().nulls_first(), Comment.id.asc())
        )
        if fetch_all_for_tree:
            stmt = stmt.limit(500)
        else:
            offset = (page - 1) * size
            stmt = stmt.where(Comment.deleted_at.is_(None)).limit(size).offset(offset)
        result = await db.execute(stmt)
        return list(result.unique().scalars().all())

    @classmethod
    async def update_comment(
        cls, post_id: int, comment_id: int, content: str, db: AsyncSession
    ) -> int:
        r = await db.execute(
            update(Comment)
            .where(
                Comment.id == comment_id,
                Comment.post_id == post_id,
                Comment.deleted_at.is_(None),
            )
            .values(content=content, updated_at=utc_now())
        )
        return r.rowcount

    @classmethod
    async def delete_comment(
        cls, post_id: int, comment_id: int, db: AsyncSession
    ) -> bool:
        r = await db.execute(
            update(Comment)
            .where(
                Comment.id == comment_id,
                Comment.post_id == post_id,
                Comment.deleted_at.is_(None),
            )
            .values(deleted_at=utc_now())
        )
        return r.rowcount > 0

    @classmethod
    async def get_liked_comment_ids_for_user(
        cls, user_id: int, comment_ids: List[int], db: AsyncSession
    ) -> Set[int]:
        if not comment_ids:
            return set()
        return await CommentLikesModel.get_liked_comment_ids_for_user(
            user_id, comment_ids, db=db
        )

    @classmethod
    async def get_like_count(cls, comment_id: int, db: AsyncSession) -> int:
        result = await db.execute(
            select(Comment.like_count).where(Comment.id == comment_id)
        )
        row = result.scalar_one_or_none()
        return row or 0

    @classmethod
    async def increment_like_count(cls, comment_id: int, db: AsyncSession) -> int:
        await db.execute(
            update(Comment)
            .where(Comment.id == comment_id)
            .values(like_count=Comment.like_count + 1)
        )
        result = await db.execute(
            select(Comment.like_count).where(Comment.id == comment_id)
        )
        return result.scalar_one_or_none() or 0

    @classmethod
    async def decrement_like_count(cls, comment_id: int, db: AsyncSession) -> int:
        await db.execute(
            update(Comment)
            .where(Comment.id == comment_id)
            .values(like_count=func.greatest(Comment.like_count - 1, 0))
        )
        result = await db.execute(
            select(Comment.like_count).where(Comment.id == comment_id)
        )
        return result.scalar_one_or_none() or 0


class CommentLikesModel:
    @classmethod
    async def get_liked_comment_ids_for_user(
        cls, user_id: int, comment_ids: List[int], db: AsyncSession
    ) -> Set[int]:
        if not comment_ids:
            return set()
        stmt = select(CommentLike.comment_id).where(
            CommentLike.user_id == user_id,
            CommentLike.comment_id.in_(comment_ids),
        )
        result = await db.execute(stmt)
        rows = result.all()
        return set(r[0] for r in rows)

    @classmethod
    async def create(cls, comment_id: int, user_id: int, db: AsyncSession) -> bool:
        stmt = (
            pg_insert(CommentLike)
            .values(comment_id=comment_id, user_id=user_id, created_at=utc_now())
            .on_conflict_do_nothing(
                index_elements=[CommentLike.comment_id, CommentLike.user_id]
            )
            .returning(CommentLike.comment_id)
        )
        result = await db.execute(stmt)
        return result.scalar_one_or_none() is not None

    @classmethod
    async def delete(cls, comment_id: int, user_id: int, db: AsyncSession) -> bool:
        r = await db.execute(
            delete(CommentLike).where(
                CommentLike.comment_id == comment_id,
                CommentLike.user_id == user_id,
            )
        )
        return r.rowcount > 0

    @classmethod
    async def has_like(cls, comment_id: int, user_id: int, db: AsyncSession) -> bool:
        stmt = (
            select(CommentLike.comment_id)
            .where(
                CommentLike.comment_id == comment_id,
                CommentLike.user_id == user_id,
            )
            .limit(1)
        )
        result = await db.execute(stmt)
        return result.scalar_one_or_none() is not None

    @classmethod
    async def increment_like_count(cls, comment_id: int, db: AsyncSession) -> int:
        await db.execute(
            update(Comment)
            .where(Comment.id == comment_id)
            .values(like_count=Comment.like_count + 1)
        )
        result = await db.execute(
            select(Comment.like_count).where(Comment.id == comment_id)
        )
        return result.scalar_one_or_none() or 0

    @classmethod
    async def decrement_like_count(cls, comment_id: int, db: AsyncSession) -> int:
        await db.execute(
            update(Comment)
            .where(Comment.id == comment_id)
            .values(like_count=func.greatest(Comment.like_count - 1, 0))
        )
        result = await db.execute(
            select(Comment.like_count).where(Comment.id == comment_id)
        )
        return result.scalar_one_or_none() or 0
