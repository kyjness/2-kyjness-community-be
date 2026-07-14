"""pg_trgm 해시태그 GIN·posts GIN fastupdate 튜닝.

Revision ID: 007_pg_trgm_search
Revises: 006_chat_dm
Create Date: 2026-05-18
"""

from collections.abc import Sequence

from alembic import op

revision: str = "007_pg_trgm_search"
down_revision: str | None = "006_chat_dm"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_GIN_FASTUPDATE = {"fastupdate": True}


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")

    op.create_index(
        "idx_hashtags_name_gin",
        "hashtags",
        ["name"],
        unique=False,
        postgresql_using="gin",
        postgresql_ops={"name": "gin_trgm_ops"},
        postgresql_with=_GIN_FASTUPDATE,
    )

    # 기존 posts GIN에 fastupdate 적용(쓰기 지연 완화). ILIKE '%…%' 플랜은 동일.
    op.drop_index("idx_posts_title_gin", table_name="posts")
    op.create_index(
        "idx_posts_title_gin",
        "posts",
        ["title"],
        unique=False,
        postgresql_using="gin",
        postgresql_ops={"title": "gin_trgm_ops"},
        postgresql_with=_GIN_FASTUPDATE,
    )
    op.drop_index("idx_posts_content_gin", table_name="posts")
    op.create_index(
        "idx_posts_content_gin",
        "posts",
        ["content"],
        unique=False,
        postgresql_using="gin",
        postgresql_ops={"content": "gin_trgm_ops"},
        postgresql_with=_GIN_FASTUPDATE,
    )


def downgrade() -> None:
    op.drop_index("idx_posts_content_gin", table_name="posts")
    op.create_index(
        "idx_posts_content_gin",
        "posts",
        ["content"],
        unique=False,
        postgresql_using="gin",
        postgresql_ops={"content": "gin_trgm_ops"},
    )
    op.drop_index("idx_posts_title_gin", table_name="posts")
    op.create_index(
        "idx_posts_title_gin",
        "posts",
        ["title"],
        unique=False,
        postgresql_using="gin",
        postgresql_ops={"title": "gin_trgm_ops"},
    )
    op.drop_index("idx_hashtags_name_gin", table_name="hashtags")
