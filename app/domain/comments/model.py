# 댓글 CRUD. Comment ORM 반환, Controller/매퍼에서 Schema로 직렬화.
from typing import List, Optional

from sqlalchemy import select, update
from sqlalchemy.orm import Session, mapped_column, relationship, joinedload
from sqlalchemy import Integer, Text, DateTime, ForeignKey

from app.db import Base, utc_now
from app.users.model import User


class Comment(Base):
    __tablename__ = "comments"

    id = mapped_column(Integer, primary_key=True, autoincrement=True)
    post_id = mapped_column(Integer, ForeignKey("posts.id", ondelete="CASCADE"), nullable=False)
    author_id = mapped_column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    content = mapped_column(Text, nullable=False)
    created_at = mapped_column(DateTime, nullable=False)
    updated_at = mapped_column(DateTime, nullable=False)
    deleted_at = mapped_column(DateTime, nullable=True)

    author = relationship(User, foreign_keys=[author_id])


class CommentsModel:
    @classmethod
    def create_comment(cls, post_id: int, user_id: int, content: str, db: Session) -> Comment:
        now = utc_now()
        c = Comment(post_id=post_id, author_id=user_id, content=content, created_at=now, updated_at=now, deleted_at=None)
        db.add(c)
        db.flush()
        return c

    @classmethod
    def get_comment_by_id(cls, comment_id: int, db: Session) -> Optional[Comment]:
        stmt = (
            select(Comment)
            .where(Comment.id == comment_id, Comment.deleted_at.is_(None))
            .options(joinedload(Comment.author).joinedload(User.profile_image))
        )
        return db.execute(stmt).unique().scalars().one_or_none()

    @classmethod
    def get_comments_by_post_id(
        cls,
        post_id: int,
        page: int = 1,
        size: int = 10,
        *,
        db: Session,
    ) -> List[Comment]:
        offset = (page - 1) * size
        stmt = (
            select(Comment)
            .where(Comment.post_id == post_id, Comment.deleted_at.is_(None))
            .options(joinedload(Comment.author).joinedload(User.profile_image))
            .order_by(Comment.id.desc())
            .limit(size)
            .offset(offset)
        )
        return list(db.execute(stmt).unique().scalars().all())

    @classmethod
    def update_comment(cls, post_id: int, comment_id: int, content: str, db: Session) -> int:
        r = db.execute(
            update(Comment)
            .where(Comment.id == comment_id, Comment.post_id == post_id, Comment.deleted_at.is_(None))
            .values(content=content, updated_at=utc_now())
        )
        return r.rowcount

    @classmethod
    def delete_comment(cls, post_id: int, comment_id: int, db: Session) -> bool:
        r = db.execute(
            update(Comment)
            .where(Comment.id == comment_id, Comment.post_id == post_id, Comment.deleted_at.is_(None))
            .values(deleted_at=utc_now())
        )
        return r.rowcount > 0
