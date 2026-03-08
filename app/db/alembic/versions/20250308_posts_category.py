"""posts 테이블에 category 컬럼 추가

Revision ID: posts_category
Revises: pg_trgm_posts_gin
Create Date: 2025-03-08

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "posts_category"
down_revision: Union[str, None] = "pg_trgm_posts_gin"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("posts", sa.Column("category", sa.String(50), nullable=True))


def downgrade() -> None:
    op.drop_column("posts", "category")
