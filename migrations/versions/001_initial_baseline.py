"""Initial Baseline (V1.0)

Revision ID: 001_initial_baseline
Revises: None
Create Date: 2026-03-25

- 스쿼시 베이스라인. 엔티티 PK/FK는 ULID 문자열 저장(String(26), Crockford Base32).
- categories / hashtags만 정수 PK(시드·클라이언트 매핑).
- posts.user_id, comments.author_id는 탈퇴 시 SET NULL (003_set_null과 동등).
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "001_initial_baseline"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_ULID = sa.String(length=26)


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")

    # --- users (profile_image FK는 images 생성 후) ---
    op.create_table(
        "users",
        sa.Column("id", _ULID, nullable=False),
        sa.Column("version", sa.Integer(), nullable=False, server_default=sa.text("1")),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("password", sa.String(length=255), nullable=False),
        sa.Column("nickname", sa.String(length=255), nullable=False),
        sa.Column("profile_image_id", _ULID, nullable=True),
        sa.Column("role", sa.String(length=20), nullable=False, server_default=sa.text("'USER'")),
        sa.Column(
            "status", sa.String(length=20), nullable=False, server_default=sa.text("'ACTIVE'")
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_users_email"), "users", ["email"], unique=True)
    op.create_index(op.f("ix_users_nickname"), "users", ["nickname"], unique=True)

    # --- images ---
    op.create_table(
        "images",
        sa.Column("id", _ULID, nullable=False),
        sa.Column("file_key", sa.String(length=255), nullable=False),
        sa.Column("file_url", sa.String(length=999), nullable=False),
        sa.Column("content_type", sa.String(length=255), nullable=True),
        sa.Column("size", sa.Integer(), nullable=True),
        sa.Column("uploader_id", _ULID, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["uploader_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_images_uploader_id"), "images", ["uploader_id"], unique=False)

    op.create_foreign_key(
        "fk_users_profile_image",
        "users",
        "images",
        ["profile_image_id"],
        ["id"],
        ondelete="SET NULL",
    )

    # --- categories / hashtags ---
    op.create_table(
        "categories",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("name", sa.String(length=50), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name", name="uq_categories_name"),
    )
    op.create_index(op.f("ix_categories_name"), "categories", ["name"], unique=False)

    op.create_table(
        "hashtags",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("name", sa.String(length=50), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name", name="uq_hashtags_name"),
    )
    op.create_index(op.f("ix_hashtags_name"), "hashtags", ["name"], unique=False)

    # --- posts ---
    op.create_table(
        "posts",
        sa.Column("id", _ULID, nullable=False),
        sa.Column("user_id", _ULID, nullable=True),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("category_id", sa.Integer(), nullable=True),
        sa.Column("view_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("like_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("comment_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("report_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("is_blinded", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False, server_default=sa.text("1")),
        sa.ForeignKeyConstraint(["category_id"], ["categories.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_posts_user_id"), "posts", ["user_id"], unique=False)
    op.create_index(op.f("ix_posts_category_id"), "posts", ["category_id"], unique=False)
    op.create_index(op.f("ix_posts_deleted_at_id"), "posts", ["deleted_at", "id"], unique=False)
    op.create_index(
        "idx_posts_title_gin",
        "posts",
        ["title"],
        unique=False,
        postgresql_using="gin",
        postgresql_ops={"title": "gin_trgm_ops"},
    )
    op.create_index(
        "idx_posts_content_gin",
        "posts",
        ["content"],
        unique=False,
        postgresql_using="gin",
        postgresql_ops={"content": "gin_trgm_ops"},
    )

    op.create_table(
        "post_hashtags",
        sa.Column("post_id", _ULID, nullable=False),
        sa.Column("hashtag_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["hashtag_id"], ["hashtags.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["post_id"], ["posts.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("post_id", "hashtag_id"),
    )

    op.create_table(
        "dog_profiles",
        sa.Column("id", _ULID, nullable=False),
        sa.Column("owner_id", _ULID, nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("breed", sa.String(length=100), nullable=False),
        sa.Column("gender", sa.String(length=20), nullable=False),
        sa.Column("birth_date", sa.Date(), nullable=False),
        sa.Column("profile_image_id", _ULID, nullable=True),
        sa.Column(
            "is_representative", sa.Boolean(), nullable=False, server_default=sa.text("false")
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["profile_image_id"], ["images.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_dog_profiles_owner_id"), "dog_profiles", ["owner_id"], unique=False)
    op.create_index(
        op.f("ix_dog_profiles_profile_image_id"),
        "dog_profiles",
        ["profile_image_id"],
        unique=False,
    )

    op.create_table(
        "post_images",
        sa.Column("id", _ULID, nullable=False),
        sa.Column("post_id", _ULID, nullable=False),
        sa.Column("image_id", _ULID, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["image_id"], ["images.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["post_id"], ["posts.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("image_id", name="uq_post_images_image_id"),
    )
    op.create_index(op.f("ix_post_images_post_id"), "post_images", ["post_id"], unique=False)
    op.create_index(op.f("ix_post_images_image_id"), "post_images", ["image_id"], unique=False)

    op.create_table(
        "post_likes",
        sa.Column("post_id", _ULID, nullable=False),
        sa.Column("user_id", _ULID, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["post_id"], ["posts.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("post_id", "user_id"),
    )

    op.create_table(
        "comments",
        sa.Column("id", _ULID, nullable=False),
        sa.Column("post_id", _ULID, nullable=False),
        sa.Column("author_id", _ULID, nullable=True),
        sa.Column("parent_id", _ULID, nullable=True),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("like_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("report_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("is_blinded", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["author_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["parent_id"], ["comments.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["post_id"], ["posts.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_comments_post_id"), "comments", ["post_id"], unique=False)
    op.create_index(op.f("ix_comments_author_id"), "comments", ["author_id"], unique=False)
    op.create_index(op.f("ix_comments_parent_id"), "comments", ["parent_id"], unique=False)

    op.create_table(
        "comment_likes",
        sa.Column("comment_id", _ULID, nullable=False),
        sa.Column("user_id", _ULID, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["comment_id"], ["comments.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("comment_id", "user_id"),
    )

    op.create_table(
        "user_blocks",
        sa.Column("blocker_id", _ULID, nullable=False),
        sa.Column("blocked_id", _ULID, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["blocker_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["blocked_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("blocker_id", "blocked_id"),
        sa.UniqueConstraint("blocker_id", "blocked_id", name="uq_user_blocks_blocker_blocked"),
    )

    op.create_table(
        "reports",
        sa.Column("id", _ULID, nullable=False),
        sa.Column("reporter_id", _ULID, nullable=False),
        sa.Column("target_type", sa.String(length=50), nullable=False),
        sa.Column("target_id", _ULID, nullable=False),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["reporter_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_reports_reporter_id"), "reports", ["reporter_id"], unique=False)

    op.alter_column("users", "version", server_default=None)
    op.alter_column("posts", "version", server_default=None)


def downgrade() -> None:
    op.drop_index(op.f("ix_reports_reporter_id"), table_name="reports")
    op.drop_table("reports")
    op.drop_table("user_blocks")
    op.drop_table("comment_likes")
    op.drop_index(op.f("ix_comments_parent_id"), table_name="comments")
    op.drop_index(op.f("ix_comments_author_id"), table_name="comments")
    op.drop_index(op.f("ix_comments_post_id"), table_name="comments")
    op.drop_table("comments")
    op.drop_table("post_likes")
    op.drop_index(op.f("ix_post_images_image_id"), table_name="post_images")
    op.drop_index(op.f("ix_post_images_post_id"), table_name="post_images")
    op.drop_table("post_images")
    op.drop_index(op.f("ix_dog_profiles_profile_image_id"), table_name="dog_profiles")
    op.drop_index(op.f("ix_dog_profiles_owner_id"), table_name="dog_profiles")
    op.drop_table("dog_profiles")
    op.drop_table("post_hashtags")
    op.drop_index("idx_posts_content_gin", table_name="posts")
    op.drop_index("idx_posts_title_gin", table_name="posts")
    op.drop_index(op.f("ix_posts_deleted_at_id"), table_name="posts")
    op.drop_index(op.f("ix_posts_category_id"), table_name="posts")
    op.drop_index(op.f("ix_posts_user_id"), table_name="posts")
    op.drop_table("posts")
    op.drop_index(op.f("ix_hashtags_name"), table_name="hashtags")
    op.drop_table("hashtags")
    op.drop_index(op.f("ix_categories_name"), table_name="categories")
    op.drop_table("categories")
    op.drop_constraint("fk_users_profile_image", "users", type_="foreignkey")
    op.drop_index(op.f("ix_images_uploader_id"), table_name="images")
    op.drop_table("images")
    op.drop_index(op.f("ix_users_nickname"), table_name="users")
    op.drop_index(op.f("ix_users_email"), table_name="users")
    op.drop_table("users")
