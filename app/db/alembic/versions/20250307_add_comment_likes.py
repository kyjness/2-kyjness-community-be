"""add comment_likes and comments.like_count

Revision ID: add_comment_likes
Revises: initial_pg
Create Date: 2025-03-07

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "add_comment_likes"
down_revision: str | None = "initial_pg"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "comments",
        sa.Column("like_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
    )
    op.create_table(
        "comment_likes",
        sa.Column("comment_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["comment_id"], ["comments.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("comment_id", "user_id"),
    )
    op.create_index(
        op.f("ix_comment_likes_comment_id"),
        "comment_likes",
        ["comment_id"],
        unique=False,
    )
    op.create_index(op.f("ix_comment_likes_user_id"), "comment_likes", ["user_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_comment_likes_user_id"), table_name="comment_likes")
    op.drop_index(op.f("ix_comment_likes_comment_id"), table_name="comment_likes")
    op.drop_table("comment_likes")
    op.drop_column("comments", "like_count")
