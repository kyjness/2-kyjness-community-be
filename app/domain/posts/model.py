# 게시글·post_images CRUD. 좋아요(PostLike)는 app.domain.likes에 있음. AsyncSession.
from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Table,
    Text,
    UniqueConstraint,
    delete,
    exists,
    func,
    or_,
    select,
    update,
)
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapped, joinedload, mapped_column, relationship, selectinload

from app.core.ids import new_ulid_str
from app.db import Base, utc_now
from app.media.model import Image
from app.users.model import DogProfile, User, UserBlock

post_hashtags = Table(
    "post_hashtags",
    Base.metadata,
    Column("post_id", String(26), ForeignKey("posts.id", ondelete="CASCADE"), primary_key=True),
    Column(
        "hashtag_id",
        Integer,
        ForeignKey("hashtags.id", ondelete="CASCADE"),
        primary_key=True,
    ),
)


class Category(Base):
    __tablename__ = "categories"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    posts: Mapped[list[Post]] = relationship("Post", back_populates="category", lazy="raise_on_sql")


class Hashtag(Base):
    __tablename__ = "hashtags"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)

    posts: Mapped[list[Post]] = relationship(
        "Post",
        secondary=post_hashtags,
        back_populates="hashtags",
        lazy="raise_on_sql",
    )


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

    id: Mapped[str] = mapped_column(String(26), primary_key=True, default=new_ulid_str)
    user_id: Mapped[str | None] = mapped_column(
        String(26), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    category_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("categories.id", ondelete="SET NULL"), nullable=True, index=True
    )
    view_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    like_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    comment_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    report_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    is_blinded: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    __mapper_args__ = {"version_id_col": version}

    user: Mapped[User | None] = relationship(User, foreign_keys=[user_id], lazy="raise_on_sql")
    category: Mapped[Category | None] = relationship(
        "Category", back_populates="posts", foreign_keys=[category_id], lazy="raise_on_sql"
    )
    post_images: Mapped[list[PostImage]] = relationship(
        "PostImage",
        back_populates="post",
        order_by="PostImage.id",
        lazy="raise_on_sql",
    )
    hashtags: Mapped[list[Hashtag]] = relationship(
        "Hashtag",
        secondary=post_hashtags,
        back_populates="posts",
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
    __table_args__ = (UniqueConstraint("image_id", name="uq_post_images_image_id"),)

    id: Mapped[str] = mapped_column(String(26), primary_key=True, default=new_ulid_str)
    post_id: Mapped[str] = mapped_column(
        String(26), ForeignKey("posts.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    image_id: Mapped[str] = mapped_column(
        String(26), ForeignKey("images.id", ondelete="CASCADE"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    post: Mapped[Post] = relationship("Post", back_populates="post_images", lazy="raise_on_sql")
    image: Mapped[Image] = relationship(Image, foreign_keys=[image_id], lazy="raise_on_sql")

    @property
    def file_url(self) -> str | None:
        return self.image.file_url if self.image else None


class PostsModel:
    MAX_POST_IMAGES = 5

    @classmethod
    async def category_exists(cls, category_id: int, *, db: AsyncSession) -> bool:
        r = await db.execute(select(exists().where(Category.id == category_id)))
        return bool(r.scalar())

    @classmethod
    async def sync_post_hashtags(
        cls,
        post_id: str,
        hashtag_names: list[str],
        *,
        db: AsyncSession,
    ) -> None:
        # 연결 테이블은 매번 초기화 후 재삽입(트랜잭션 내 원자성 확보).
        await db.execute(delete(post_hashtags).where(post_hashtags.c.post_id == post_id))

        if not hashtag_names:
            return

        # 1) 이미 존재하는 해시태그 ID 수집.
        result = await db.execute(
            select(Hashtag.id, Hashtag.name).where(Hashtag.name.in_(hashtag_names))
        )
        existing_by_name = {row[1]: row[0] for row in result.all()}
        missing = set(hashtag_names) - set(existing_by_name.keys())

        # 2) 없는 해시태그는 생성(유니크 충돌 시 무시).
        if missing:
            await db.execute(
                pg_insert(Hashtag)
                .values([{"name": n} for n in missing])
                .on_conflict_do_nothing(index_elements=[Hashtag.name])
            )

        # 3) 최종 ID 다시 조회.
        result2 = await db.execute(
            select(Hashtag.id, Hashtag.name).where(Hashtag.name.in_(hashtag_names))
        )
        existing_by_name = {row[1]: row[0] for row in result2.all()}
        hashtag_ids = [existing_by_name[n] for n in hashtag_names if n in existing_by_name]

        # 4) M:N 연결 삽입(중복은 ON CONFLICT DO NOTHING).
        if hashtag_ids:
            await db.execute(
                pg_insert(post_hashtags)
                .values([{"post_id": post_id, "hashtag_id": hid} for hid in hashtag_ids])
                .on_conflict_do_nothing(index_elements=["post_id", "hashtag_id"])
            )

    @classmethod
    async def create_post(
        cls,
        user_id: str,
        title: str,
        content: str,
        image_ids: list[str] | None = None,
        category_id: int | None = None,
        hashtag_names: list[str] | None = None,
        *,
        db: AsyncSession,
    ) -> str:
        image_ids = image_ids or []
        now = utc_now()
        post = Post(
            user_id=user_id,
            title=title,
            content=content,
            category_id=category_id,
            created_at=now,
            updated_at=now,
            deleted_at=None,
        )
        db.add(post)
        await db.flush()
        limited = image_ids[: cls.MAX_POST_IMAGES]
        if limited:
            db.add_all(PostImage(post_id=post.id, image_id=iid, created_at=now) for iid in limited)
        if hashtag_names is not None:
            await cls.sync_post_hashtags(post.id, hashtag_names, db=db)
        return post.id

    @classmethod
    async def get_post_by_id(
        cls,
        post_id: str,
        db: AsyncSession,
        current_user_id: str | None = None,
    ) -> Post | None:
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
                joinedload(Post.category),
                selectinload(Post.hashtags),
                selectinload(Post.post_images).joinedload(PostImage.image),
            )
        )
        if current_user_id is not None:
            block_exists = exists(1).where(
                UserBlock.blocker_id == current_user_id,
                UserBlock.blocked_id == Post.user_id,
            )
            stmt = stmt.where(~block_exists)
        result = await db.execute(stmt)
        return result.scalars().one_or_none()

    @classmethod
    async def get_post_by_id_with_like_flag(
        cls,
        post_id: str,
        user_id: str,
        db: AsyncSession,
    ) -> tuple[Post, bool] | None:
        """로그인 사용자 기준 게시글 상세 + 좋아요 여부를 단일 SELECT로 조회."""
        # 순환 참조 여지를 줄이기 위해 지연 임포트.
        from app.domain.likes.model import PostLike

        is_liked_expr = (
            exists(1).where(PostLike.post_id == Post.id, PostLike.user_id == user_id)
        ).label("is_liked")
        stmt = (
            select(Post, is_liked_expr)
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
                joinedload(Post.category),
                selectinload(Post.hashtags),
                selectinload(Post.post_images).joinedload(PostImage.image),
            )
        )
        block_exists = exists(1).where(
            UserBlock.blocker_id == user_id,
            UserBlock.blocked_id == Post.user_id,
        )
        stmt = stmt.where(~block_exists)
        result = await db.execute(stmt)
        row = result.unique().one_or_none()
        if row is None:
            return None
        return row[0], bool(row[1])

    @classmethod
    async def get_post_author_id(cls, post_id: str, db: AsyncSession) -> str | None:
        result = await db.execute(
            select(Post.user_id).where(Post.id == post_id, Post.deleted_at.is_(None))
        )
        return result.scalar_one_or_none()

    @classmethod
    async def get_titles_by_ids(cls, post_ids: list[str], db: AsyncSession) -> dict[str, str]:
        if not post_ids:
            return {}
        result = await db.execute(
            select(Post.id, Post.title).where(Post.id.in_(post_ids), Post.deleted_at.is_(None))
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
        category_id: int | None = None,
        current_user_id: str | None = None,
    ) -> tuple[list[Post], bool]:
        offset = (page - 1) * size
        fetch_limit = size + 1
        stmt = (
            select(Post)
            .where(Post.deleted_at.is_(None), Post.is_blinded.is_(False))
            .options(
                joinedload(Post.user).joinedload(User.profile_image),
                joinedload(Post.user).selectinload(User.dogs).joinedload(DogProfile.profile_image),
                joinedload(Post.category),
                selectinload(Post.hashtags),
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
        if category_id is not None:
            stmt = stmt.where(Post.category_id == category_id)
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
        category_id: int | None = None,
        current_user_id: str | None = None,
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
        if category_id is not None:
            stmt = stmt.where(Post.category_id == category_id)
        result = await db.execute(stmt)
        row = result.scalar_one_or_none()
        return row or 0

    @classmethod
    async def update_post(
        cls,
        post_id: str,
        title: str | None = None,
        content: str | None = None,
        image_ids: list[str] | None = None,
        category_id: int | None = None,
        hashtag_names: list[str] | None = None,
        *,
        db: AsyncSession,
    ) -> tuple[list[str], list[str]] | None:
        now = utc_now()
        post_obj = (
            await db.execute(
                select(Post).where(
                    Post.id == post_id,
                    Post.deleted_at.is_(None),
                )
            )
        ).scalar_one_or_none()
        if post_obj is None:
            return None

        if title is not None:
            post_obj.title = title
        if content is not None:
            post_obj.content = content
        if category_id is not None:
            post_obj.category_id = category_id
        post_obj.updated_at = now

        if hashtag_names is not None:
            await cls.sync_post_hashtags(post_id, hashtag_names, db=db)

        released_ids: list[str] = []
        added_ids: list[str] = []
        if image_ids is not None:
            old_result = await db.execute(
                select(PostImage.image_id).where(PostImage.post_id == post_id)
            )
            old = old_result.scalars().all()
            old_image_ids = set(old) if old else set()
            new_image_ids_set = set(image_ids[: cls.MAX_POST_IMAGES])
            to_add = new_image_ids_set - old_image_ids
            released_ids = list(old_image_ids - new_image_ids_set)
            if to_add:
                to_add_list = list(to_add)
                added_ids = to_add_list
                db.add_all(
                    PostImage(post_id=post_id, image_id=iid, created_at=now) for iid in to_add_list
                )
            if released_ids:
                await db.execute(
                    delete(PostImage).where(
                        PostImage.post_id == post_id, PostImage.image_id.in_(released_ids)
                    )
                )
        return released_ids, added_ids

    @classmethod
    async def delete_post(cls, post_id: str, db: AsyncSession) -> tuple[bool, list[str]]:
        from app.comments.model import Comment
        from app.domain.likes.model import PostLikesModel

        # 1) 게시글 soft-delete를 원자적으로 선점.
        # 이미 삭제된 게시글이면 추가 작업 없이 (False, []) 반환해 멱등성 보장.
        r_post = await db.execute(
            update(Post)
            .where(
                Post.id == post_id,
                Post.deleted_at.is_(None),
            )
            .values(deleted_at=utc_now(), updated_at=utc_now())
            .returning(Post.id)
        )
        if r_post.scalar_one_or_none() is None:
            return (False, [])

        # 2) 연관 리소스 정리(같은 트랜잭션).
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
        return (True, image_ids)

    @classmethod
    async def increment_view_count(cls, post_id: str, db: AsyncSession) -> bool:
        result = await db.execute(
            update(Post)
            .where(
                Post.id == post_id,
                Post.deleted_at.is_(None),
            )
            .values(view_count=Post.view_count + 1, updated_at=utc_now())
            .returning(Post.id)
        )
        return result.scalar_one_or_none() is not None

    @classmethod
    async def increment_report_count(cls, post_id: str, db: AsyncSession) -> int | None:
        result = await db.execute(
            update(Post)
            .where(
                Post.id == post_id,
                Post.deleted_at.is_(None),
            )
            .values(report_count=Post.report_count + 1, updated_at=utc_now())
            .returning(Post.report_count)
        )
        row = result.one_or_none()
        return row[0] if row is not None else None

    @classmethod
    async def set_blinded(cls, post_id: str, db: AsyncSession) -> bool:
        result = await db.execute(
            update(Post)
            .where(
                Post.id == post_id,
                Post.deleted_at.is_(None),
            )
            .values(is_blinded=True, updated_at=utc_now())
            .returning(Post.id)
        )
        return result.scalar_one_or_none() is not None

    @classmethod
    async def unblind_post(cls, post_id: str, db: AsyncSession) -> bool:
        """블라인드만 해제. report_count는 유지하여 관리자 목록에 계속 노출."""
        result = await db.execute(
            update(Post)
            .where(
                Post.id == post_id,
                Post.deleted_at.is_(None),
            )
            .values(is_blinded=False, updated_at=utc_now())
            .returning(Post.id)
        )
        return result.scalar_one_or_none() is not None

    @classmethod
    async def reset_reports(cls, post_id: str, db: AsyncSession) -> bool:
        """신고 무시: report_count=0, is_blinded=False 로 초기화."""
        result = await db.execute(
            update(Post)
            .where(
                Post.id == post_id,
                Post.deleted_at.is_(None),
            )
            .values(report_count=0, is_blinded=False, updated_at=utc_now())
            .returning(Post.id)
        )
        return result.scalar_one_or_none() is not None

    @classmethod
    async def get_reported_posts(
        cls,
        page: int = 1,
        size: int = 20,
        *,
        db: AsyncSession,
    ) -> tuple[list[Post], int]:
        offset = (page - 1) * size
        stmt_base = (
            select(Post)
            .where(Post.deleted_at.is_(None))
            .where(Post.report_count > 0)
            .options(
                joinedload(Post.user).joinedload(User.profile_image),
                joinedload(Post.user).selectinload(User.dogs).joinedload(DogProfile.profile_image),
                joinedload(Post.category),
                selectinload(Post.hashtags),
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
    async def get_like_count(cls, post_id: str, db: AsyncSession) -> int:
        result = await db.execute(select(Post.like_count).where(Post.id == post_id))
        row = result.scalar_one_or_none()
        return row or 0

    @classmethod
    async def increment_like_count(cls, post_id: str, db: AsyncSession) -> int:
        result = await db.execute(
            update(Post)
            .where(Post.id == post_id)
            .values(like_count=Post.like_count + 1, updated_at=utc_now())
            .returning(Post.like_count)
        )
        row = result.one_or_none()
        return row[0] if row is not None else 0

    @classmethod
    async def decrement_like_count(cls, post_id: str, db: AsyncSession) -> int:
        result = await db.execute(
            update(Post)
            .where(Post.id == post_id)
            .values(like_count=func.greatest(Post.like_count - 1, 0), updated_at=utc_now())
            .returning(Post.like_count)
        )
        row = result.one_or_none()
        return row[0] if row is not None else 0

    @classmethod
    async def increment_comment_count(cls, post_id: str, db: AsyncSession) -> bool:
        result = await db.execute(
            update(Post)
            .where(Post.id == post_id)
            .values(comment_count=Post.comment_count + 1, updated_at=utc_now())
            .returning(Post.id)
        )
        return result.scalar_one_or_none() is not None

    @classmethod
    async def decrement_comment_count(cls, post_id: str, db: AsyncSession) -> bool:
        result = await db.execute(
            update(Post)
            .where(Post.id == post_id)
            .values(comment_count=func.greatest(Post.comment_count - 1, 0), updated_at=utc_now())
            .returning(Post.id)
        )
        return result.scalar_one_or_none() is not None
