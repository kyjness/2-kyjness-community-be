# 게시글·post_images CRUD. 좋아요(PostLike)는 app.domain.likes에 있음. AsyncSession.
from typing import List, Optional

from sqlalchemy import or_, select, update, delete, func, Index
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import relationship, joinedload, selectinload, mapped_column
from sqlalchemy import String, Integer, DateTime, ForeignKey, Text

from app.db import Base, utc_now
from app.media.model import Image, MediaModel
from app.users.model import User, DogProfile


class Post(Base):
    __tablename__ = "posts"
    __table_args__ = (
        Index(
            "idx_posts_title_gin",
            "title",
            postgresql_using="gin",
            postgresql_ops={"title": "gin_trgm_ops"},
        ),
        Index(
            "idx_posts_content_gin",
            "content",
            postgresql_using="gin",
            postgresql_ops={"content": "gin_trgm_ops"},
        ),
    )

    id = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    title = mapped_column(String(255), nullable=False)
    content = mapped_column(Text, nullable=False)
    category = mapped_column(String(50), nullable=True)
    view_count = mapped_column(Integer, default=0, nullable=False)
    like_count = mapped_column(Integer, default=0, nullable=False)
    comment_count = mapped_column(Integer, default=0, nullable=False)
    created_at = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at = mapped_column(DateTime(timezone=True), nullable=False)
    deleted_at = mapped_column(DateTime(timezone=True), nullable=True)

    user = relationship(User, foreign_keys=[user_id])
    post_images = relationship(
        "PostImage", back_populates="post", order_by="PostImage.id"
    )

    @property
    def author(self):
        return self.user

    @property
    def files(self):
        return self.post_images or []


class PostImage(Base):
    __tablename__ = "post_images"

    id = mapped_column(Integer, primary_key=True, autoincrement=True)
    post_id = mapped_column(
        Integer, ForeignKey("posts.id", ondelete="RESTRICT"), nullable=False
    )
    image_id = mapped_column(
        Integer, ForeignKey("images.id", ondelete="CASCADE"), nullable=False
    )
    created_at = mapped_column(DateTime(timezone=True), nullable=False)

    post = relationship("Post", back_populates="post_images")
    image = relationship(Image, foreign_keys=[image_id])

    @property
    def file_url(self) -> Optional[str]:
        return self.image.file_url if self.image else None


class PostsModel:
    MAX_POST_IMAGES = 5

    @classmethod
    async def create_post(
        cls,
        user_id: int,
        title: str,
        content: str,
        image_ids: Optional[List[int]] = None,
        *,
        db: AsyncSession,
    ) -> int:
        image_ids = image_ids or []
        now = utc_now()
        post = Post(
            user_id=user_id,
            title=title,
            content=content,
            created_at=now,
            updated_at=now,
            deleted_at=None,
        )
        db.add(post)
        await db.flush()
        for iid in image_ids[: cls.MAX_POST_IMAGES]:
            db.add(PostImage(post_id=post.id, image_id=iid, created_at=now))
        for iid in image_ids[: cls.MAX_POST_IMAGES]:
            await MediaModel.increment_ref_count(iid, db=db)
        return post.id

    @classmethod
    async def get_post_by_id(cls, post_id: int, db: AsyncSession) -> Optional["Post"]:
        stmt = (
            select(Post)
            .where(Post.id == post_id, Post.deleted_at.is_(None))
            .options(
                joinedload(Post.user).options(
                    joinedload(User.profile_image),
                    selectinload(User.dogs).joinedload(DogProfile.profile_image),
                ),
                joinedload(Post.post_images).joinedload(PostImage.image),
            )
        )
        result = await db.execute(stmt)
        return result.unique().scalars().one_or_none()

    @classmethod
    async def get_post_author_id(cls, post_id: int, db: AsyncSession) -> Optional[int]:
        result = await db.execute(
            select(Post.user_id).where(Post.id == post_id, Post.deleted_at.is_(None))
        )
        return result.scalar_one_or_none()

    @classmethod
    async def get_all_posts(
        cls,
        page: int = 1,
        size: int = 20,
        *,
        db: AsyncSession,
        search_q: Optional[str] = None,
        sort: Optional[str] = None,
    ) -> tuple[List["Post"], bool]:
        offset = (page - 1) * size
        fetch_limit = size + 1
        stmt = (
            select(Post)
            .where(Post.deleted_at.is_(None))
            .options(
                joinedload(Post.user).joinedload(User.profile_image),
                joinedload(Post.user)
                .selectinload(User.dogs)
                .joinedload(DogProfile.profile_image),
                selectinload(Post.post_images).joinedload(PostImage.image),
            )
        )
        if search_q and search_q.strip():
            pattern = f"%{search_q.strip()}%"
            stmt = stmt.where(
                or_(Post.title.ilike(pattern), Post.content.ilike(pattern))
            )
        if sort == "popular":
            stmt = stmt.order_by(Post.like_count.desc(), Post.created_at.desc())
        elif sort == "views":
            stmt = stmt.order_by(Post.view_count.desc(), Post.created_at.desc())
        elif sort == "oldest":
            stmt = stmt.order_by(Post.created_at.asc())
        else:
            stmt = stmt.order_by(Post.created_at.desc())
        stmt = stmt.limit(fetch_limit).offset(offset)
        result = await db.execute(stmt)
        posts = result.unique().scalars().all()
        has_more = len(posts) > size
        posts = posts[:size]
        return posts, has_more

    @classmethod
    async def get_posts_count(
        cls,
        *,
        db: AsyncSession,
        search_q: Optional[str] = None,
    ) -> int:
        """삭제되지 않은 게시글 전체 개수 (페이지네이션 total용). search_q 시 검색 조건 반영."""
        stmt = select(func.count(Post.id)).where(Post.deleted_at.is_(None))
        if search_q and search_q.strip():
            pattern = f"%{search_q.strip()}%"
            stmt = stmt.where(
                or_(Post.title.ilike(pattern), Post.content.ilike(pattern))
            )
        result = await db.execute(stmt)
        row = result.scalar_one_or_none()
        return row or 0

    @classmethod
    async def update_post(
        cls,
        post_id: int,
        title: Optional[str] = None,
        content: Optional[str] = None,
        image_ids: Optional[List[int]] = None,
        *,
        db: AsyncSession,
    ) -> Optional[List[int]]:
        result = await db.execute(
            select(Post).where(Post.id == post_id, Post.deleted_at.is_(None))
        )
        post = result.scalar_one_or_none()
        if not post:
            return None
        if title is not None:
            await db.execute(
                update(Post)
                .where(Post.id == post_id)
                .values(title=title, updated_at=utc_now())
            )
        if content is not None:
            await db.execute(
                update(Post)
                .where(Post.id == post_id)
                .values(content=content, updated_at=utc_now())
            )
        to_delete: List[int] = []
        if image_ids is not None:
            old_result = await db.execute(
                select(PostImage.image_id).where(PostImage.post_id == post_id)
            )
            old = old_result.scalars().all()
            old_image_ids = set(old) if old else set()
            new_image_ids_set = set(image_ids[: cls.MAX_POST_IMAGES])
            to_add = new_image_ids_set - old_image_ids
            to_delete = list(old_image_ids - new_image_ids_set)
            now = utc_now()
            for iid in to_add:
                db.add(PostImage(post_id=post_id, image_id=iid, created_at=now))
            if to_delete:
                await db.execute(
                    delete(PostImage).where(
                        PostImage.post_id == post_id, PostImage.image_id.in_(to_delete)
                    )
                )
            for iid in to_add:
                await MediaModel.increment_ref_count(iid, db=db)
        return to_delete

    @classmethod
    async def delete_post(
        cls, post_id: int, db: AsyncSession
    ) -> tuple[bool, List[int]]:
        from app.comments.model import Comment
        from app.domain.likes.model import PostLikesModel

        await db.execute(
            update(Comment)
            .where(Comment.post_id == post_id, Comment.deleted_at.is_(None))
            .values(deleted_at=utc_now())
        )
        await PostLikesModel.delete_by_post_id(post_id, db=db)
        img_result = await db.execute(
            select(PostImage.image_id).where(PostImage.post_id == post_id)
        )
        image_ids = list(img_result.scalars().all()) or []
        await db.execute(delete(PostImage).where(PostImage.post_id == post_id))
        r = await db.execute(
            update(Post)
            .where(Post.id == post_id, Post.deleted_at.is_(None))
            .values(deleted_at=utc_now())
        )
        return (r.rowcount > 0, image_ids)

    @classmethod
    async def increment_view_count(cls, post_id: int, db: AsyncSession) -> bool:
        await db.execute(
            update(Post)
            .where(Post.id == post_id, Post.deleted_at.is_(None))
            .values(view_count=Post.view_count + 1)
        )
        return True

    @classmethod
    async def get_like_count(cls, post_id: int, db: AsyncSession) -> int:
        result = await db.execute(select(Post.like_count).where(Post.id == post_id))
        row = result.scalar_one_or_none()
        return row or 0

    @classmethod
    async def increment_like_count(cls, post_id: int, db: AsyncSession) -> int:
        stmt = (
            update(Post)
            .where(Post.id == post_id)
            .values(like_count=Post.like_count + 1)
            .returning(Post.like_count)
        )
        result = await db.execute(stmt)
        row = result.one_or_none()
        return row[0] if row is not None else 0

    @classmethod
    async def decrement_like_count(cls, post_id: int, db: AsyncSession) -> int:
        stmt = (
            update(Post)
            .where(Post.id == post_id)
            .values(like_count=func.greatest(Post.like_count - 1, 0))
            .returning(Post.like_count)
        )
        result = await db.execute(stmt)
        row = result.one_or_none()
        return row[0] if row is not None else 0

    @classmethod
    async def increment_comment_count(cls, post_id: int, db: AsyncSession) -> bool:
        await db.execute(
            update(Post)
            .where(Post.id == post_id)
            .values(comment_count=Post.comment_count + 1)
        )
        return True

    @classmethod
    async def decrement_comment_count(cls, post_id: int, db: AsyncSession) -> bool:
        await db.execute(
            update(Post)
            .where(Post.id == post_id)
            .values(comment_count=func.greatest(Post.comment_count - 1, 0))
        )
        return True
