"""comments.parent_id (대댓글 1-depth)

Revision ID: comments_parent_id
Revises: add_comment_likes
Create Date: 2025-03-07

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "comments_parent_id"
down_revision: str | None = "datetime_tz"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "comments",
        sa.Column("parent_id", sa.Integer(), nullable=True),
    )
    op.create_foreign_key(
        "fk_comments_parent_id",
        "comments",
        "comments",
        ["parent_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_index(op.f("ix_comments_parent_id"), "comments", ["parent_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_comments_parent_id"), table_name="comments")
    op.drop_constraint("fk_comments_parent_id", "comments", type_="foreignkey")
    op.drop_column("comments", "parent_id")
