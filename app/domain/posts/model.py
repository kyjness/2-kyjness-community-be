# 게시글·좋아요·post_images CRUD. Post, PostImage, Like 모델.
from typing import List, Optional

from sqlalchemy import select, update, delete, func
from sqlalchemy.orm import Session, relationship, joinedload, selectinload, mapped_column
from sqlalchemy import String, Integer, DateTime, ForeignKey
from sqlalchemy.dialects.mysql import MEDIUMTEXT

from app.db import Base, utc_now
from app.media.model import Image, MediaModel
from app.users.model import User, DogProfile


class Post(Base):
    __tablename__ = "posts"

    id = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id = mapped_column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    title = mapped_column(String(255), nullable=False)
    content = mapped_column(MEDIUMTEXT, nullable=False)
    view_count = mapped_column(Integer, default=0, nullable=False)
    like_count = mapped_column(Integer, default=0, nullable=False)
    comment_count = mapped_column(Integer, default=0, nullable=False)
    created_at = mapped_column(DateTime, nullable=False)
    updated_at = mapped_column(DateTime, nullable=False)
    deleted_at = mapped_column(DateTime, nullable=True)

    user = relationship(User, foreign_keys=[user_id])
    post_images = relationship("PostImage", back_populates="post", order_by="PostImage.id")

    @property
    def author(self):
        return self.user

    @property
    def files(self):
        return self.post_images or []


class PostImage(Base):
    __tablename__ = "post_images"

    id = mapped_column(Integer, primary_key=True, autoincrement=True)
    post_id = mapped_column(Integer, ForeignKey("posts.id", ondelete="RESTRICT"), nullable=False)
    image_id = mapped_column(Integer, ForeignKey("images.id", ondelete="CASCADE"), nullable=False)
    created_at = mapped_column(DateTime, nullable=False)

    post = relationship("Post", back_populates="post_images")
    image = relationship(Image, foreign_keys=[image_id])

    @property
    def file_url(self) -> Optional[str]:
        return self.image.file_url if self.image else None


class Like(Base):
    __tablename__ = "likes"

    post_id = mapped_column(Integer, ForeignKey("posts.id", ondelete="CASCADE"), primary_key=True)
    user_id = mapped_column(Integer, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    created_at = mapped_column(DateTime, nullable=False)


class PostsModel:
    MAX_POST_IMAGES = 5

    @classmethod
    def create_post(
        cls,
        user_id: int,
        title: str,
        content: str,
        image_ids: Optional[List[int]] = None,
        *,
        db: Session,
    ) -> int:
        image_ids = image_ids or []
        now = utc_now()
        post = Post(user_id=user_id, title=title, content=content, created_at=now, updated_at=now, deleted_at=None)
        db.add(post)
        db.flush()
        for iid in image_ids[: cls.MAX_POST_IMAGES]:
            db.add(PostImage(post_id=post.id, image_id=iid, created_at=now))
        for iid in image_ids[: cls.MAX_POST_IMAGES]:
            MediaModel.increment_ref_count(iid, db=db)
        return post.id

    @classmethod
    def get_post_by_id(cls, post_id: int, db: Session) -> Optional["Post"]:
        stmt = (
            select(Post)
            .where(Post.id == post_id, Post.deleted_at.is_(None))
            .options(
                joinedload(Post.user).joinedload(User.profile_image),
                joinedload(Post.user).selectinload(User.dogs).joinedload(DogProfile.profile_image),
                joinedload(Post.post_images).joinedload(PostImage.image),
            )
        )
        return db.execute(stmt).unique().scalars().one_or_none()

    @classmethod
    def get_post_author_id(cls, post_id: int, db: Session) -> Optional[int]:
        row = db.execute(select(Post.user_id).where(Post.id == post_id, Post.deleted_at.is_(None))).scalar_one_or_none()
        return row

    @classmethod
    def get_all_posts(
        cls,
        page: int = 1,
        size: int = 20,
        *,
        db: Session,
    ) -> tuple[List["Post"], bool]:
        offset = (page - 1) * size
        fetch_limit = size + 1
        stmt = (
            select(Post)
            .where(Post.deleted_at.is_(None))
            .order_by(Post.id.desc())
            .limit(fetch_limit)
            .offset(offset)
            .options(
                joinedload(Post.user).joinedload(User.profile_image),
                joinedload(Post.user).selectinload(User.dogs).joinedload(DogProfile.profile_image),
                selectinload(Post.post_images).joinedload(PostImage.image),
            )
        )
        posts = db.execute(stmt).unique().scalars().all()
        has_more = len(posts) > size
        posts = posts[:size]
        return posts, has_more

    @classmethod
    def get_posts_count(cls, *, db: Session) -> int:
        """삭제되지 않은 게시글 전체 개수 (페이지네이션 total용)."""
        row = db.execute(
            select(func.count(Post.id)).where(Post.deleted_at.is_(None))
        ).scalar_one_or_none()
        return row or 0

    @classmethod
    def update_post(
        cls,
        post_id: int,
        title: Optional[str] = None,
        content: Optional[str] = None,
        image_ids: Optional[List[int]] = None,
        *,
        db: Session,
    ) -> bool:
        post = db.execute(select(Post).where(Post.id == post_id, Post.deleted_at.is_(None))).scalar_one_or_none()
        if not post:
            return False
        if title is not None:
            db.execute(update(Post).where(Post.id == post_id).values(title=title, updated_at=utc_now()))
        if content is not None:
            db.execute(update(Post).where(Post.id == post_id).values(content=content, updated_at=utc_now()))
        if image_ids is not None:
            old = db.execute(select(PostImage.image_id).where(PostImage.post_id == post_id)).scalars().all()
            old_image_ids = set(old)
            new_image_ids_set = set(image_ids[: cls.MAX_POST_IMAGES])
            to_add = new_image_ids_set - old_image_ids
            to_delete = old_image_ids - new_image_ids_set
            now = utc_now()
            for iid in to_add:
                db.add(PostImage(post_id=post_id, image_id=iid, created_at=now))
            if to_delete:
                db.execute(delete(PostImage).where(PostImage.post_id == post_id, PostImage.image_id.in_(to_delete)))
            for iid in to_add:
                MediaModel.increment_ref_count(iid, db=db)
            for iid in to_delete:
                MediaModel.decrement_ref_count(iid, db=db)
        return True

    @classmethod
    def delete_post(cls, post_id: int, db: Session) -> bool:
        from app.comments.model import Comment
        db.execute(update(Comment).where(Comment.post_id == post_id, Comment.deleted_at.is_(None)).values(deleted_at=utc_now()))
        db.execute(delete(Like).where(Like.post_id == post_id))
        image_ids = db.execute(select(PostImage.image_id).where(PostImage.post_id == post_id)).scalars().all()
        db.execute(delete(PostImage).where(PostImage.post_id == post_id))
        for iid in image_ids:
            MediaModel.decrement_ref_count(iid, db=db)
        r = db.execute(update(Post).where(Post.id == post_id, Post.deleted_at.is_(None)).values(deleted_at=utc_now()))
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
        like = Like(post_id=post_id, user_id=user_id, created_at=utc_now())
        db.add(like)
        db.flush()
        return {"post_id": post_id, "user_id": user_id}

    @classmethod
    def delete_like(cls, post_id: int, user_id: int, db: Session) -> bool:
        r = db.execute(delete(Like).where(Like.post_id == post_id, Like.user_id == user_id))
        return r.rowcount > 0
