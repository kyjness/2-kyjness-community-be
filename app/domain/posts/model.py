# 게시글·post_images ORM 정의. 쿼리/트랜잭션 로직은 repository.py.
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
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.ids import new_ulid_str
from app.db.base_class import Base
from app.media.model import Image
from app.users.model import DogProfile, User

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
        Index(
            "idx_posts_feed_latest",
            created_at.desc(),
            postgresql_where=(deleted_at.is_(None)) & (is_blinded.is_(False)),
        ),
    )

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
