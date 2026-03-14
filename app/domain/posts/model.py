# 게시글·post_images CRUD. 좋아요(PostLike)는 app.domain.likes에 있음. AsyncSession.
from typing import Optional

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    delete,
    exists,
    func,
    or_,
    select,
    update,
)
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload, mapped_column, relationship, selectinload

from app.db import Base, utc_now
from app.media.model import Image, MediaModel
from app.users.model import DogProfile, User, UserBlock


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
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    title = mapped_column(String(255), nullable=False)
    content = mapped_column(Text, nullable=False)
    category = mapped_column(String(50), nullable=True)
    view_count = mapped_column(Integer, default=0, nullable=False)
    like_count = mapped_column(Integer, default=0, nullable=False)
    comment_count = mapped_column(Integer, default=0, nullable=False)
    report_count = mapped_column(Integer, default=0, nullable=False)
    is_blinded = mapped_column(Boolean, default=False, nullable=False)
    created_at = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at = mapped_column(DateTime(timezone=True), nullable=False)
    deleted_at = mapped_column(DateTime(timezone=True), nullable=True)

    user = relationship(User, foreign_keys=[user_id], lazy="raise_on_sql")
    post_images = relationship(
        "PostImage",
        back_populates="post",
        order_by="PostImage.id",
        lazy="raise_on_sql",
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
        Integer, ForeignKey("posts.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    image_id = mapped_column(
        Integer, ForeignKey("images.id", ondelete="CASCADE"), nullable=False, index=True
    )
    created_at = mapped_column(DateTime(timezone=True), nullable=False)

    post = relationship("Post", back_populates="post_images", lazy="raise_on_sql")
    image = relationship(Image, foreign_keys=[image_id], lazy="raise_on_sql")

    @property
    def file_url(self) -> str | None:
        return self.image.file_url if self.image else None


class PostsModel:
    MAX_POST_IMAGES = 5

    @classmethod
    async def create_post(
        cls,
        user_id: int,
        title: str,
        content: str,
        image_ids: list[int] | None = None,
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
        limited = image_ids[: cls.MAX_POST_IMAGES]
        if limited:
            db.add_all(PostImage(post_id=post.id, image_id=iid, created_at=now) for iid in limited)
            await MediaModel.increment_ref_count_bulk(limited, db=db)
        return post.id

    @classmethod
    async def get_post_by_id(
        cls,
        post_id: int,
        db: AsyncSession,
        current_user_id: int | None = None,
    ) -> Optional["Post"]:
        stmt = (
            select(Post)
            .where(
                Post.id == post_id,
                Post.deleted_at.is_(None),
                Post.is_blinded.is_(False),
            )
            .options(
                joinedload(Post.user).options(
                    joinedload(User.profile_image),
                    selectinload(User.dogs).joinedload(DogProfile.profile_image),
                ),
                joinedload(Post.post_images).joinedload(PostImage.image),
            )
        )
        if current_user_id is not None:
            block_exists = exists(1).where(
                UserBlock.blocker_id == current_user_id,
                UserBlock.blocked_id == Post.user_id,
            )
            stmt = stmt.where(~block_exists)
        result = await db.execute(stmt)
        return result.unique().scalars().one_or_none()

    @classmethod
    async def get_post_author_id(cls, post_id: int, db: AsyncSession) -> int | None:
        result = await db.execute(
            select(Post.user_id).where(Post.id == post_id, Post.deleted_at.is_(None))
        )
        return result.scalar_one_or_none()

    @classmethod
    async def get_titles_by_ids(
        cls, post_ids: list[int], db: AsyncSession
    ) -> dict[int, str]:
        if not post_ids:
            return {}
        result = await db.execute(
            select(Post.id, Post.title).where(
                Post.id.in_(post_ids), Post.deleted_at.is_(None)
            )
        )
        return {row[0]: row[1] for row in result.all()}

    @classmethod
    async def get_all_posts(
        cls,
        page: int = 1,
        size: int = 20,
        *,
        db: AsyncSession,
        search_q: str | None = None,
        sort: str | None = None,
        current_user_id: int | None = None,
    ) -> tuple[list["Post"], bool]:
        offset = (page - 1) * size
        fetch_limit = size + 1
        stmt = (
            select(Post)
            .where(Post.deleted_at.is_(None), Post.is_blinded.is_(False))
            .options(
                joinedload(Post.user).joinedload(User.profile_image),
                joinedload(Post.user).selectinload(User.dogs).joinedload(DogProfile.profile_image),
                selectinload(Post.post_images).joinedload(PostImage.image),
            )
        )
        if current_user_id is not None:
            block_exists = exists(1).where(
                UserBlock.blocker_id == current_user_id,
                UserBlock.blocked_id == Post.user_id,
            )
            stmt = stmt.where(~block_exists)
        if search_q and search_q.strip():
            pattern = f"%{search_q.strip()}%"
            stmt = stmt.where(or_(Post.title.ilike(pattern), Post.content.ilike(pattern)))
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
        rows = result.unique().scalars().all()
        has_more = len(rows) > size
        return list(rows[:size]), has_more

    @classmethod
    async def get_posts_count(
        cls,
        *,
        db: AsyncSession,
        search_q: str | None = None,
        current_user_id: int | None = None,
    ) -> int:
        """삭제되지 않은 게시글 전체 개수 (페이지네이션 total용). search_q 시 검색 조건 반영."""
        stmt = select(func.count(Post.id)).where(
            Post.deleted_at.is_(None), Post.is_blinded.is_(False)
        )
        if current_user_id is not None:
            block_exists = exists(1).where(
                UserBlock.blocker_id == current_user_id,
                UserBlock.blocked_id == Post.user_id,
            )
            stmt = stmt.where(~block_exists)
        if search_q and search_q.strip():
            pattern = f"%{search_q.strip()}%"
            stmt = stmt.where(or_(Post.title.ilike(pattern), Post.content.ilike(pattern)))
        result = await db.execute(stmt)
        row = result.scalar_one_or_none()
        return row or 0

    @classmethod
    async def update_post(
        cls,
        post_id: int,
        title: str | None = None,
        content: str | None = None,
        image_ids: list[int] | None = None,
        *,
        db: AsyncSession,
    ) -> list[int] | None:
        now = utc_now()
        values: dict = {"updated_at": now}
        if title is not None:
            values["title"] = title
        if content is not None:
            values["content"] = content
        r = await db.execute(
            update(Post)
            .where(Post.id == post_id, Post.deleted_at.is_(None))
            .values(**values)
            .returning(Post.id)
        )
        if r.one_or_none() is None:
            return None
        to_delete: list[int] = []
        if image_ids is not None:
            old_result = await db.execute(
                select(PostImage.image_id).where(PostImage.post_id == post_id)
            )
            old = old_result.scalars().all()
            old_image_ids = set(old) if old else set()
            new_image_ids_set = set(image_ids[: cls.MAX_POST_IMAGES])
            to_add = new_image_ids_set - old_image_ids
            to_delete = list(old_image_ids - new_image_ids_set)
            if to_add:
                to_add_list = list(to_add)
                db.add_all(
                    PostImage(post_id=post_id, image_id=iid, created_at=now) for iid in to_add_list
                )
            if to_delete:
                await db.execute(
                    delete(PostImage).where(
                        PostImage.post_id == post_id, PostImage.image_id.in_(to_delete)
                    )
                )
            # 실무에서는 update(...).where(id.in_(image_ids)) 방식의 벌크 업데이트가 더 효율적임.
            if to_add:
                await MediaModel.increment_ref_count_bulk(list(to_add), db=db)
        return to_delete

    @classmethod
    async def delete_post(cls, post_id: int, db: AsyncSession) -> tuple[bool, list[int]]:
        from app.comments.model import Comment
        from app.domain.likes.model import PostLikesModel

        await db.execute(
            update(Comment)
            .where(Comment.post_id == post_id, Comment.deleted_at.is_(None))
            .values(deleted_at=utc_now())
        )
        await PostLikesModel.delete_by_post_id(post_id, db=db)
        r_img = await db.execute(
            delete(PostImage).where(PostImage.post_id == post_id).returning(PostImage.image_id)
        )
        image_ids = list(r_img.scalars().all()) or []
        r = await db.execute(
            update(Post)
            .where(Post.id == post_id, Post.deleted_at.is_(None))
            .values(deleted_at=utc_now())
            .returning(Post.id)
        )
        return (r.scalar_one_or_none() is not None, image_ids)

    @classmethod
    async def increment_view_count(cls, post_id: int, db: AsyncSession) -> bool:
        await db.execute(
            update(Post)
            .where(Post.id == post_id, Post.deleted_at.is_(None))
            .values(view_count=Post.view_count + 1)
        )
        return True

    @classmethod
    async def increment_report_count(cls, post_id: int, db: AsyncSession) -> int | None:
        stmt = (
            update(Post)
            .where(Post.id == post_id, Post.deleted_at.is_(None))
            .values(report_count=Post.report_count + 1)
            .returning(Post.report_count)
        )
        result = await db.execute(stmt)
        row = result.one_or_none()
        return row[0] if row is not None else None

    @classmethod
    async def set_blinded(cls, post_id: int, db: AsyncSession) -> bool:
        r = await db.execute(
            update(Post)
            .where(Post.id == post_id, Post.deleted_at.is_(None))
            .values(is_blinded=True, updated_at=utc_now())
            .returning(Post.id)
        )
        return r.scalar_one_or_none() is not None

    @classmethod
    async def unblind_post(cls, post_id: int, db: AsyncSession) -> bool:
        """블라인드만 해제. report_count는 유지하여 관리자 목록에 계속 노출."""
        r = await db.execute(
            update(Post)
            .where(Post.id == post_id)
            .values(is_blinded=False, updated_at=utc_now())
            .returning(Post.id)
        )
        return r.scalar_one_or_none() is not None

    @classmethod
    async def reset_reports(cls, post_id: int, db: AsyncSession) -> bool:
        """신고 무시: report_count=0, is_blinded=False 로 초기화."""
        r = await db.execute(
            update(Post)
            .where(Post.id == post_id, Post.deleted_at.is_(None))
            .values(
                report_count=0,
                is_blinded=False,
                updated_at=utc_now(),
            )
            .returning(Post.id)
        )
        return r.scalar_one_or_none() is not None

    @classmethod
    async def get_reported_posts(
        cls,
        page: int = 1,
        size: int = 20,
        *,
        db: AsyncSession,
    ) -> tuple[list["Post"], int]:
        offset = (page - 1) * size
        stmt_base = (
            select(Post)
            .where(Post.deleted_at.is_(None))
            .where(Post.report_count > 0)
            .options(
                joinedload(Post.user).joinedload(User.profile_image),
                joinedload(Post.user).selectinload(User.dogs).joinedload(DogProfile.profile_image),
                selectinload(Post.post_images).joinedload(PostImage.image),
            )
            .order_by(Post.report_count.desc(), Post.created_at.desc())
        )
        count_stmt = (
            select(func.count(Post.id))
            .where(Post.deleted_at.is_(None))
            .where(Post.report_count > 0)
        )
        total = (await db.execute(count_stmt)).scalar_one_or_none() or 0
        stmt = stmt_base.limit(size).offset(offset)
        result = await db.execute(stmt)
        posts = list(result.unique().scalars().all())
        return posts, total

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
            update(Post).where(Post.id == post_id).values(comment_count=Post.comment_count + 1)
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
