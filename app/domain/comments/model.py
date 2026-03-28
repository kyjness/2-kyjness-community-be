# 댓글 CRUD. Comment ORM 반환, Controller/매퍼에서 Schema로 직렬화. AsyncSession.

from datetime import datetime
from typing import NamedTuple

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    and_,
    delete,
    exists,
    func,
    or_,
    select,
    update,
)
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapped, joinedload, mapped_column, relationship

from app.core.ids import new_ulid_str
from app.db.base_class import Base, utc_now
from app.posts.model import Post
from app.users.model import DogProfile, User, UserBlock


class CommentAuthorPermissionRow(NamedTuple):
    comment_id: str | None
    comment_post_id: str | None
    comment_author_id: str | None


class Comment(Base):
    __tablename__ = "comments"

    id: Mapped[str] = mapped_column(String(26), primary_key=True, default=new_ulid_str)
    post_id: Mapped[str] = mapped_column(
        String(26), ForeignKey("posts.id", ondelete="CASCADE"), nullable=False, index=True
    )
    author_id: Mapped[str | None] = mapped_column(
        String(26), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    parent_id: Mapped[str | None] = mapped_column(
        String(26), ForeignKey("comments.id", ondelete="CASCADE"), nullable=True, index=True
    )
    content: Mapped[str] = mapped_column(Text, nullable=False)
    like_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    report_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    is_blinded: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    author: Mapped[User | None] = relationship(User, foreign_keys=[author_id], lazy="raise_on_sql")
    parent: Mapped["Comment | None"] = relationship(
        "Comment",
        remote_side="Comment.id",
        back_populates="replies",
        foreign_keys=[parent_id],
        lazy="raise_on_sql",
    )
    replies: Mapped[list["Comment"]] = relationship(
        "Comment",
        back_populates="parent",
        foreign_keys=[parent_id],
        lazy="raise_on_sql",
    )
    likes: Mapped[list["CommentLike"]] = relationship(
        "CommentLike",
        back_populates="comment",
        foreign_keys="CommentLike.comment_id",
        lazy="raise_on_sql",
    )


class CommentLike(Base):
    __tablename__ = "comment_likes"

    comment_id: Mapped[str] = mapped_column(
        String(26), ForeignKey("comments.id", ondelete="CASCADE"), primary_key=True
    )
    user_id: Mapped[str] = mapped_column(
        String(26), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    comment: Mapped[Comment] = relationship(Comment, back_populates="likes", lazy="raise_on_sql")
    user: Mapped[User] = relationship(User, foreign_keys=[user_id], lazy="raise_on_sql")


class CommentsModel:
    @classmethod
    async def load_comment_author_permission_row(
        cls,
        post_id: str,
        comment_id: str,
        *,
        db: AsyncSession,
        include_deleted_comment: bool = False,
    ) -> CommentAuthorPermissionRow | None:
        """경로의 게시글이 존재·미삭제이면 1행. Comment는 LEFT JOIN (단일 SELECT).

        - include_deleted_comment=False: 삭제된 댓글은 JOIN에서 제외(미존재와 동일).
        - include_deleted_comment=True: 삭제된 댓글도 매칭(삭제 API 멱등).
        """
        join_on = [Comment.id == comment_id]
        if not include_deleted_comment:
            join_on.append(Comment.deleted_at.is_(None))
        stmt = (
            select(Comment.id, Comment.post_id, Comment.author_id)
            .select_from(Post)
            .outerjoin(Comment, and_(*join_on))
            .where(Post.id == post_id, Post.deleted_at.is_(None))
        )
        result = await db.execute(stmt)
        row = result.one_or_none()
        if row is None:
            return None
        cid, c_post_id, c_author_id = row
        return CommentAuthorPermissionRow(
            comment_id=cid,
            comment_post_id=c_post_id,
            comment_author_id=c_author_id,
        )

    @classmethod
    async def create_comment(
        cls,
        post_id: str,
        user_id: str,
        content: str,
        db: AsyncSession,
        parent_id: str | None = None,
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
        cls, comment_id: str, db: AsyncSession, include_deleted: bool = False
    ) -> Comment | None:
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
        post_id: str,
        page: int = 1,
        size: int = 10,
        *,
        db: AsyncSession,
        fetch_all_for_tree: bool = False,
        current_user_id: str | None = None,
    ) -> list[Comment]:
        stmt = (
            select(Comment)
            .where(
                Comment.post_id == post_id,
                Comment.is_blinded.is_(False),
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
        if current_user_id is not None:
            block_exists = exists(1).where(
                UserBlock.blocker_id == current_user_id,
                UserBlock.blocked_id == Comment.author_id,
            )
            stmt = stmt.where(~block_exists)
        if fetch_all_for_tree:
            stmt = stmt.limit(500)
        else:
            offset = (page - 1) * size
            stmt = stmt.where(Comment.deleted_at.is_(None)).limit(size).offset(offset)
        result = await db.execute(stmt)
        return list(result.unique().scalars().all())

    @classmethod
    async def update_comment(
        cls, post_id: str, comment_id: str, content: str, db: AsyncSession
    ) -> int:
        r = await db.execute(
            update(Comment)
            .where(
                Comment.id == comment_id,
                Comment.post_id == post_id,
                Comment.deleted_at.is_(None),
            )
            .values(content=content, updated_at=utc_now())
            .returning(Comment.id)
        )
        return len(list(r.scalars().all()))

    @classmethod
    async def delete_comment(cls, post_id: str, comment_id: str, db: AsyncSession) -> bool:
        r = await db.execute(
            update(Comment)
            .where(
                Comment.id == comment_id,
                Comment.post_id == post_id,
                Comment.deleted_at.is_(None),
            )
            .values(deleted_at=utc_now())
            .returning(Comment.id)
        )
        return r.scalar_one_or_none() is not None

    @classmethod
    async def get_liked_comment_ids_for_user(
        cls, user_id: str, comment_ids: list[str], db: AsyncSession
    ) -> set[str]:
        if not comment_ids:
            return set()
        return await CommentLikesModel.get_liked_comment_ids_for_user(user_id, comment_ids, db=db)

    @classmethod
    async def get_like_count(cls, comment_id: str, db: AsyncSession) -> int:
        result = await db.execute(select(Comment.like_count).where(Comment.id == comment_id))
        row = result.scalar_one_or_none()
        return row or 0

    @classmethod
    async def get_reported_comments(
        cls,
        page: int = 1,
        size: int = 20,
        *,
        db: AsyncSession,
    ) -> tuple[list["Comment"], int]:
        """report_count > 0 인 댓글 목록 (관리자 대시보드용). author 로드."""
        offset = (page - 1) * size
        stmt = (
            select(Comment)
            .where(Comment.report_count > 0)
            .where(Comment.deleted_at.is_(None))
            .options(
                joinedload(Comment.author).joinedload(User.profile_image),
            )
            .order_by(Comment.report_count.desc(), Comment.created_at.desc())
        )
        count_stmt = (
            select(func.count(Comment.id))
            .where(Comment.report_count > 0)
            .where(Comment.deleted_at.is_(None))
        )
        total = (await db.execute(count_stmt)).scalar_one_or_none() or 0
        stmt = stmt.limit(size).offset(offset)
        result = await db.execute(stmt)
        comments = list(result.unique().scalars().all())
        return comments, total

    @classmethod
    async def increment_report_count(cls, comment_id: str, db: AsyncSession) -> int | None:
        stmt = (
            update(Comment)
            .where(Comment.id == comment_id)
            .values(report_count=Comment.report_count + 1)
            .returning(Comment.report_count)
        )
        result = await db.execute(stmt)
        row = result.one_or_none()
        return row[0] if row is not None else None

    @classmethod
    async def set_blinded(cls, comment_id: str, db: AsyncSession) -> bool:
        r = await db.execute(
            update(Comment)
            .where(Comment.id == comment_id)
            .values(is_blinded=True, updated_at=utc_now())
            .returning(Comment.id)
        )
        return r.scalar_one_or_none() is not None

    @classmethod
    async def unblind_comment(cls, comment_id: str, db: AsyncSession) -> bool:
        r = await db.execute(
            update(Comment)
            .where(Comment.id == comment_id, Comment.deleted_at.is_(None))
            .values(is_blinded=False, updated_at=utc_now())
            .returning(Comment.id)
        )
        return r.scalar_one_or_none() is not None

    @classmethod
    async def reset_reports(cls, comment_id: str, db: AsyncSession) -> bool:
        r = await db.execute(
            update(Comment)
            .where(Comment.id == comment_id, Comment.deleted_at.is_(None))
            .values(report_count=0, is_blinded=False, updated_at=utc_now())
            .returning(Comment.id)
        )
        return r.scalar_one_or_none() is not None

    @classmethod
    async def increment_like_count(cls, comment_id: str, db: AsyncSession) -> int:
        result = await db.execute(
            update(Comment)
            .where(Comment.id == comment_id)
            .values(like_count=Comment.like_count + 1)
            .returning(Comment.like_count)
        )
        row = result.one_or_none()
        return row[0] if row is not None else 0

    @classmethod
    async def decrement_like_count(cls, comment_id: str, db: AsyncSession) -> int:
        result = await db.execute(
            update(Comment)
            .where(Comment.id == comment_id)
            .values(like_count=func.greatest(Comment.like_count - 1, 0))
            .returning(Comment.like_count)
        )
        row = result.one_or_none()
        return row[0] if row is not None else 0


class CommentLikesModel:
    @classmethod
    async def get_liked_comment_ids_for_user(
        cls, user_id: str, comment_ids: list[str], db: AsyncSession
    ) -> set[str]:
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
    async def create(cls, comment_id: str, user_id: str, db: AsyncSession) -> bool:
        stmt = (
            pg_insert(CommentLike)
            .values(comment_id=comment_id, user_id=user_id, created_at=utc_now())
            .on_conflict_do_nothing(index_elements=[CommentLike.comment_id, CommentLike.user_id])
            .returning(CommentLike.comment_id)
        )
        result = await db.execute(stmt)
        return result.scalar_one_or_none() is not None

    @classmethod
    async def delete(cls, comment_id: str, user_id: str, db: AsyncSession) -> bool:
        r = await db.execute(
            delete(CommentLike)
            .where(
                CommentLike.comment_id == comment_id,
                CommentLike.user_id == user_id,
            )
            .returning(CommentLike.comment_id)
        )
        return r.scalar_one_or_none() is not None

    @classmethod
    async def has_like(cls, comment_id: str, user_id: str, db: AsyncSession) -> bool:
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
    async def increment_like_count(cls, comment_id: str, db: AsyncSession) -> int:
        result = await db.execute(
            update(Comment)
            .where(Comment.id == comment_id)
            .values(like_count=Comment.like_count + 1)
            .returning(Comment.like_count)
        )
        row = result.one_or_none()
        return row[0] if row is not None else 0

    @classmethod
    async def decrement_like_count(cls, comment_id: str, db: AsyncSession) -> int:
        result = await db.execute(
            update(Comment)
            .where(Comment.id == comment_id)
            .values(like_count=func.greatest(Comment.like_count - 1, 0))
            .returning(Comment.like_count)
        )
        row = result.one_or_none()
        return row[0] if row is not None else 0
