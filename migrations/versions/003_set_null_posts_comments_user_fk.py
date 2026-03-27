"""Set NULL on user FK for posts/comments (historical).

Revision ID: 003_set_null_posts_comments_user_fk
Revises: 003_fix_alembic_version_len
Create Date: 2026-03-26

- 초기 Integer PK 시절 마이그레이션. 현재 001_initial_baseline에 posts.user_id / comments.author_id
  nullable + ON DELETE SET NULL이 이미 포함됨.
- 기존 Alembic 리비전 체인 유지를 위해 no-op으로 둠.
"""

from __future__ import annotations

from collections.abc import Sequence

revision: str = "003_set_null_posts_comments_user_fk"
down_revision: str | None = "003_fix_alembic_version_len"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
