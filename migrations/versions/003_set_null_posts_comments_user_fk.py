"""Set NULL on user FK for posts/comments.

Revision ID: 003_set_null_posts_comments_user_fk
Revises: 002_seed_categories
Create Date: 2026-03-26
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "003_set_null_posts_comments_user_fk"
down_revision: str | None = "003_fix_alembic_version_len"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1) 컬럼 nullable 변경 (FK drop 전에 수행/후에 수행 모두 가능하나, 명시적으로 먼저 NULL 허용)
    op.alter_column("posts", "user_id", existing_type=sa.Integer(), nullable=True)
    op.alter_column("comments", "author_id", existing_type=sa.Integer(), nullable=True)

    # 2) 기존 FK(CASCADE) 제거 → SET NULL로 재생성
    # Postgres 기본 네이밍: {table}_{column}_fkey
    op.drop_constraint("posts_user_id_fkey", "posts", type_="foreignkey")
    op.drop_constraint("comments_author_id_fkey", "comments", type_="foreignkey")

    op.create_foreign_key(
        "posts_user_id_fkey",
        "posts",
        "users",
        ["user_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_foreign_key(
        "comments_author_id_fkey",
        "comments",
        "users",
        ["author_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint("comments_author_id_fkey", "comments", type_="foreignkey")
    op.drop_constraint("posts_user_id_fkey", "posts", type_="foreignkey")

    op.create_foreign_key(
        "posts_user_id_fkey",
        "posts",
        "users",
        ["user_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_foreign_key(
        "comments_author_id_fkey",
        "comments",
        "users",
        ["author_id"],
        ["id"],
        ondelete="CASCADE",
    )

    op.alter_column("comments", "author_id", existing_type=sa.Integer(), nullable=False)
    op.alter_column("posts", "user_id", existing_type=sa.Integer(), nullable=False)

