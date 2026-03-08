"""pg_trgm 확장 및 posts title/content GIN 인덱스 (한글 검색 최적화)

Revision ID: pg_trgm_posts_gin
Revises: rename_likes_post_likes
Create Date: 2025-03-08

"""

from typing import Sequence, Union

from alembic import op


revision: str = "pg_trgm_posts_gin"
down_revision: Union[str, None] = "rename_likes_post_likes"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm;")
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_posts_title_gin "
        "ON posts USING gin (title gin_trgm_ops);"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_posts_content_gin "
        "ON posts USING gin (content gin_trgm_ops);"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_posts_content_gin;")
    op.execute("DROP INDEX IF EXISTS idx_posts_title_gin;")
    op.execute("DROP EXTENSION IF EXISTS pg_trgm;")
