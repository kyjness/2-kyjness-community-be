from datetime import datetime
from typing import List, Optional

from sqlalchemy import select, update, func
from sqlalchemy.orm import Session, mapped_column
from sqlalchemy import Integer, Text, DateTime, ForeignKey

from app.core.database import Base
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


class CommentsModel:
    @classmethod
    def create_comment(cls, post_id: int, user_id: int, content: str, db: Session) -> dict:
        now = datetime.now()
        c = Comment(post_id=post_id, author_id=user_id, content=content, created_at=now, updated_at=now, deleted_at=None)
        db.add(c)
        db.flush()
        return {"id": c.id, "post_id": post_id, "author_id": user_id, "content": content, "created_at": now}

    @classmethod
    def find_comment_by_id(cls, comment_id: int, db: Session) -> Optional[dict]:
        row = db.execute(select(Comment).where(Comment.id == comment_id, Comment.deleted_at.is_(None))).scalar_one_or_none()
        if not row:
            return None
        return {"id": row.id, "post_id": row.post_id, "author_id": row.author_id, "content": row.content, "created_at": row.created_at}

    @classmethod
    def get_comments_by_post_id(cls, post_id: int, page: int = 1, size: int = 10, *, db: Session) -> List[dict]:
        offset = (page - 1) * size
        rows = (
            db.execute(
                select(Comment, User.id.label("author_user_id"), User.nickname.label("author_nickname"), User.profile_image_url.label("author_profile_image_url"))
                .join(User, Comment.author_id == User.id)
                .where(Comment.post_id == post_id, Comment.deleted_at.is_(None), User.deleted_at.is_(None))
                .order_by(Comment.id.desc())
                .limit(size)
                .offset(offset)
            )
            .all()
        )
        return [
            {
                "id": r[0].id,
                "post_id": r[0].post_id,
                "author_id": r[0].author_id,
                "content": r[0].content,
                "created_at": r[0].created_at,
                "author_user_id": r[1],
                "author_nickname": r[2],
                "author_profile_image_url": (r[3] or "").strip() or "",
            }
            for r in rows
        ]

    @classmethod
    def get_comment_count_by_post_id(cls, post_id: int, db: Session) -> int:
        row = db.execute(select(func.count(Comment.id)).where(Comment.post_id == post_id, Comment.deleted_at.is_(None))).scalar()
        return row or 0

    @classmethod
    def update_comment(cls, post_id: int, comment_id: int, content: str, db: Session) -> int:
        r = db.execute(
            update(Comment)
            .where(Comment.id == comment_id, Comment.post_id == post_id, Comment.deleted_at.is_(None))
            .values(content=content, updated_at=datetime.now())
        )
        return r.rowcount

    @classmethod
    def withdraw_comment(cls, post_id: int, comment_id: int, db: Session) -> bool:
        r = db.execute(
            update(Comment)
            .where(Comment.id == comment_id, Comment.post_id == post_id, Comment.deleted_at.is_(None))
            .values(deleted_at=datetime.now())
        )
        return r.rowcount > 0
