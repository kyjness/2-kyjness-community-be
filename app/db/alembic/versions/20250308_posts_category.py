"""posts 테이블에 category 컬럼 추가

Revision ID: posts_category
Revises: pg_trgm_posts_gin
Create Date: 2025-03-08

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "posts_category"
down_revision: str | None = "pg_trgm_posts_gin"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("posts", sa.Column("category", sa.String(50), nullable=True))


def downgrade() -> None:
    op.drop_column("posts", "category")
