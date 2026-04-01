"""add idx_posts_feed_latest

Revision ID: caabca5fb0ad
Revises: 003_set_null_posts_comments_user_fk
Create Date: 2026-04-01 10:14:45.287053

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "caabca5fb0ad"
down_revision: str | None = "003_set_null_posts_comments_user_fk"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_index(
        "idx_posts_feed_latest",
        "posts",
        [sa.text("created_at DESC")],
        unique=False,
        postgresql_where=sa.text("deleted_at IS NULL AND is_blinded IS FALSE"),
    )


def downgrade() -> None:
    op.drop_index("idx_posts_feed_latest", table_name="posts")
