import logging
from datetime import datetime
from typing import List, Optional

from sqlalchemy import select, update, delete, func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, relationship, joinedload, mapped_column
from sqlalchemy import String, Integer, Text, DateTime, ForeignKey

from app.core.database import Base
from app.media.model import Image
from app.users.model import User

logger = logging.getLogger(__name__)


class Post(Base):
    __tablename__ = "posts"

    id = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id = mapped_column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    title = mapped_column(String(255), nullable=False)
    content = mapped_column(Text, nullable=False)
    view_count = mapped_column(Integer, default=0, nullable=False)
    like_count = mapped_column(Integer, default=0, nullable=False)
    comment_count = mapped_column(Integer, default=0, nullable=False)
    created_at = mapped_column(DateTime, nullable=False)
    updated_at = mapped_column(DateTime, nullable=False)
    deleted_at = mapped_column(DateTime, nullable=True)

    user = relationship(User, foreign_keys=[user_id])
    post_images = relationship("PostImage", back_populates="post", order_by="PostImage.id")


class PostImage(Base):
    __tablename__ = "post_images"

    id = mapped_column(Integer, primary_key=True, autoincrement=True)
    post_id = mapped_column(Integer, ForeignKey("posts.id", ondelete="CASCADE"), nullable=False)
    image_id = mapped_column(Integer, ForeignKey("images.id", ondelete="CASCADE"), nullable=False)
    created_at = mapped_column(DateTime, nullable=False)

    post = relationship("Post", back_populates="post_images")
    image = relationship(Image, foreign_keys=[image_id])


class Like(Base):
    __tablename__ = "likes"

    post_id = mapped_column(Integer, ForeignKey("posts.id", ondelete="CASCADE"), primary_key=True)
    user_id = mapped_column(Integer, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    created_at = mapped_column(DateTime, nullable=False)


class PostsModel:
    MAX_POST_IMAGES = 5

    @classmethod
    def create_post(cls, user_id: int, title: str, content: str, image_ids: Optional[List[int]] = None, *, db: Session) -> int:
        image_ids = image_ids or []
        now = datetime.now()
        post = Post(user_id=user_id, title=title, content=content, created_at=now, updated_at=now, deleted_at=None)
        db.add(post)
        db.flush()
        for iid in image_ids[: cls.MAX_POST_IMAGES]:
            db.add(PostImage(post_id=post.id, image_id=iid, created_at=now))
        return post.id

    @classmethod
    def find_post_by_id(cls, post_id: int, db: Session) -> Optional["Post"]:
        stmt = (
            select(Post)
            .where(Post.id == post_id, Post.deleted_at.is_(None))
            .options(
                joinedload(Post.user),
                joinedload(Post.post_images).joinedload(PostImage.image),
            )
        )
        return db.execute(stmt).unique().scalar_one_or_none()

    @classmethod
    def get_post_author_id(cls, post_id: int, db: Session) -> Optional[int]:
        row = db.execute(select(Post.user_id).where(Post.id == post_id, Post.deleted_at.is_(None))).scalar_one_or_none()
        return row

    @classmethod
    def get_all_posts(cls, page: int = 1, size: int = 20, *, db: Session) -> tuple[List["Post"], bool]:
        offset = (page - 1) * size
        fetch_limit = size + 1
        stmt = (
            select(Post)
            .where(Post.deleted_at.is_(None))
            .order_by(Post.id.desc())
            .limit(fetch_limit)
            .offset(offset)
            .options(
                joinedload(Post.user),
                joinedload(Post.post_images).joinedload(PostImage.image),
            )
        )
        posts = db.execute(stmt).unique().scalars().all()
        has_more = len(posts) > size
        posts = posts[:size]
        return posts, has_more

    @classmethod
    def update_post(cls, post_id: int, title: Optional[str] = None, content: Optional[str] = None, image_ids: Optional[List[int]] = None, *, db: Session) -> bool:
        post = db.execute(select(Post).where(Post.id == post_id, Post.deleted_at.is_(None))).scalar_one_or_none()
        if not post:
            return False
        if title is not None:
            db.execute(update(Post).where(Post.id == post_id).values(title=title, updated_at=datetime.now()))
        if content is not None:
            db.execute(update(Post).where(Post.id == post_id).values(content=content, updated_at=datetime.now()))
        if image_ids is not None:
            old = db.execute(select(PostImage.image_id).where(PostImage.post_id == post_id)).scalars().all()
            old_image_ids = {r[0] for r in old}
            new_image_ids_set = set(image_ids[: cls.MAX_POST_IMAGES])
            to_add = new_image_ids_set - old_image_ids
            to_remove = old_image_ids - new_image_ids_set
            now = datetime.now()
            for iid in to_add:
                db.add(PostImage(post_id=post_id, image_id=iid, created_at=now))
            if to_remove:
                db.execute(delete(PostImage).where(PostImage.post_id == post_id, PostImage.image_id.in_(to_remove)))
            for img_id in to_remove:
                other = db.execute(select(PostImage.id).where(PostImage.image_id == img_id).limit(1)).first()
                if not other:
                    db.execute(update(Image).where(Image.id == img_id, Image.deleted_at.is_(None)).values(deleted_at=datetime.now()))
        return True

    @classmethod
    def withdraw_post(cls, post_id: int, db: Session) -> bool:
        from app.comments.model import Comment
        db.execute(update(Comment).where(Comment.post_id == post_id, Comment.deleted_at.is_(None)).values(deleted_at=datetime.now()))
        db.execute(delete(Like).where(Like.post_id == post_id))
        img_rows = db.execute(select(PostImage.image_id).where(PostImage.post_id == post_id)).scalars().all()
        image_ids = [r[0] for r in img_rows]
        db.execute(delete(PostImage).where(PostImage.post_id == post_id))
        for img_id in image_ids:
            other = db.execute(select(PostImage.id).where(PostImage.image_id == img_id).limit(1)).first()
            if not other:
                db.execute(update(Image).where(Image.id == img_id, Image.deleted_at.is_(None)).values(deleted_at=datetime.now()))
        r = db.execute(update(Post).where(Post.id == post_id, Post.deleted_at.is_(None)).values(deleted_at=datetime.now()))
        return r.rowcount > 0

    @classmethod
    def increment_view_count(cls, post_id: int, db: Session) -> bool:
        db.execute(update(Post).where(Post.id == post_id, Post.deleted_at.is_(None)).values(view_count=Post.view_count + 1))
        return True

    @classmethod
    def get_like_count(cls, post_id: int, db: Session) -> int:
        row = db.execute(select(Post.like_count).where(Post.id == post_id)).scalar_one_or_none()
        return row or 0

    @classmethod
    def increment_like_count(cls, post_id: int, db: Session) -> int:
        db.execute(update(Post).where(Post.id == post_id).values(like_count=Post.like_count + 1))
        row = db.execute(select(Post.like_count).where(Post.id == post_id)).scalar_one_or_none()
        return row or 0

    @classmethod
    def decrement_like_count(cls, post_id: int, db: Session) -> int:
        db.execute(update(Post).where(Post.id == post_id).values(like_count=func.greatest(Post.like_count - 1, 0)))
        row = db.execute(select(Post.like_count).where(Post.id == post_id)).scalar_one_or_none()
        return row or 0

    @classmethod
    def increment_comment_count(cls, post_id: int, db: Session) -> bool:
        db.execute(update(Post).where(Post.id == post_id).values(comment_count=Post.comment_count + 1))
        return True

    @classmethod
    def decrement_comment_count(cls, post_id: int, db: Session) -> bool:
        db.execute(update(Post).where(Post.id == post_id).values(comment_count=func.greatest(Post.comment_count - 1, 0)))
        return True


class PostLikesModel:
    @classmethod
    def add_like(cls, post_id: int, user_id: int, *, db: Session) -> Optional[dict]:
        try:
            now = datetime.now()
            like = Like(post_id=post_id, user_id=user_id, created_at=now)
            db.add(like)
            db.flush()
            return {"post_id": post_id, "user_id": user_id}
        except IntegrityError:
            db.expunge(like)
            return None
        except Exception as e:
            logger.exception("likes INSERT 실패: %s", e)
            raise

    @classmethod
    def remove_like(cls, post_id: int, user_id: int, db: Session) -> bool:
        r = db.execute(delete(Like).where(Like.post_id == post_id, Like.user_id == user_id))
        return r.rowcount > 0
