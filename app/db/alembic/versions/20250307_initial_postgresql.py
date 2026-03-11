"""initial PostgreSQL schema (users, images, dog_profiles, posts, post_images, comments, likes)

Revision ID: initial_pg
Revises:
Create Date: 2025-03-07

- Boolean -> BOOLEAN, Integer autoincrement -> SERIAL/IDENTITY.
- No sessions table (JWT+Redis only).
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "initial_pg"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("password", sa.String(255), nullable=False),
        sa.Column("nickname", sa.String(255), nullable=False),
        sa.Column("profile_image_id", sa.Integer(), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default=sa.text("'ACTIVE'")),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_users_email"), "users", ["email"], unique=True)
    op.create_index(op.f("ix_users_nickname"), "users", ["nickname"], unique=True)

    op.create_table(
        "images",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("file_key", sa.String(255), nullable=False),
        sa.Column("file_url", sa.String(999), nullable=False),
        sa.Column("content_type", sa.String(255), nullable=True),
        sa.Column("size", sa.Integer(), nullable=True),
        sa.Column("uploader_id", sa.Integer(), nullable=True),
        sa.Column("ref_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("signup_token_hash", sa.String(64), nullable=True),
        sa.Column("signup_expires_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["uploader_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_images_uploader_id"), "images", ["uploader_id"], unique=False)
    op.create_index(
        op.f("ix_images_signup_expires_at"),
        "images",
        ["signup_expires_at"],
        unique=False,
    )

    op.create_foreign_key(
        "fk_users_profile_image",
        "users",
        "images",
        ["profile_image_id"],
        ["id"],
        ondelete="SET NULL",
    )

    op.create_table(
        "dog_profiles",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("owner_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("breed", sa.String(100), nullable=False),
        sa.Column("gender", sa.String(20), nullable=False),
        sa.Column("birth_date", sa.Date(), nullable=False),
        sa.Column("profile_image_id", sa.Integer(), nullable=True),
        sa.Column(
            "is_representative",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["profile_image_id"], ["images.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_dog_profiles_owner_id"), "dog_profiles", ["owner_id"], unique=False)

    op.create_table(
        "posts",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("view_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("like_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("comment_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_posts_user_id"), "posts", ["user_id"], unique=False)
    op.create_index(op.f("ix_posts_deleted_at_id"), "posts", ["deleted_at", "id"], unique=False)

    op.create_table(
        "post_images",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("post_id", sa.Integer(), nullable=False),
        sa.Column("image_id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["image_id"], ["images.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["post_id"], ["posts.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("image_id", name="uq_post_images_image_id"),
    )
    op.create_index(op.f("ix_post_images_post_id"), "post_images", ["post_id"], unique=False)
    op.create_index(op.f("ix_post_images_image_id"), "post_images", ["image_id"], unique=False)

    op.create_table(
        "comments",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("post_id", sa.Integer(), nullable=False),
        sa.Column("author_id", sa.Integer(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["author_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["post_id"], ["posts.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_comments_post_id"), "comments", ["post_id"], unique=False)
    op.create_index(op.f("ix_comments_author_id"), "comments", ["author_id"], unique=False)

    op.create_table(
        "likes",
        sa.Column("post_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["post_id"], ["posts.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("post_id", "user_id"),
    )


def downgrade() -> None:
    op.drop_table("likes")
    op.drop_index(op.f("ix_comments_author_id"), table_name="comments")
    op.drop_index(op.f("ix_comments_post_id"), table_name="comments")
    op.drop_table("comments")
    op.drop_index(op.f("ix_post_images_image_id"), table_name="post_images")
    op.drop_index(op.f("ix_post_images_post_id"), table_name="post_images")
    op.drop_table("post_images")
    op.drop_index(op.f("ix_posts_deleted_at_id"), table_name="posts")
    op.drop_index(op.f("ix_posts_user_id"), table_name="posts")
    op.drop_table("posts")
    op.drop_index(op.f("ix_dog_profiles_owner_id"), table_name="dog_profiles")
    op.drop_table("dog_profiles")
    op.drop_constraint("fk_users_profile_image", "users", type_="foreignkey")
    op.drop_index(op.f("ix_images_signup_expires_at"), table_name="images")
    op.drop_index(op.f("ix_images_uploader_id"), table_name="images")
    op.drop_table("images")
    op.drop_index(op.f("ix_users_nickname"), table_name="users")
    op.drop_index(op.f("ix_users_email"), table_name="users")
    op.drop_table("users")
