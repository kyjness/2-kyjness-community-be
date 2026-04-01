"""add idx_posts_feed_latest

Revision ID: caabca5fb0ad
Revises: 003_set_null_posts_comments_user_fk
Create Date: 2026-04-01 10:14:45.287053

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "caabca5fb0ad"
down_revision: Union[str, None] = "003_set_null_posts_comments_user_fk"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


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
