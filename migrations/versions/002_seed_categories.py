"""Seed default categories.

Revision ID: 002_seed_categories
Revises: 001_initial_baseline
Create Date: 2026-03-26

- posts.category_id는 FK(categories.id)라서 기본 카테고리(1~5)가 없으면 글 작성이 실패함.
- 운영/로컬/테스트에서 id를 고정해 UI/클라이언트 매핑과 일치시키기 위해 명시적으로 삽입.
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "002_seed_categories"
down_revision: str | None = "001_initial_baseline"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # id 고정 (프론트 select 매핑과 일치)
    op.execute(
        """
        INSERT INTO categories (id, name, description) VALUES
          (1, '자유게시판', NULL),
          (2, '질문있어요', NULL),
          (3, '강아지자랑', NULL),
          (4, '정보공유', NULL),
          (5, '나눔해요', NULL)
        ON CONFLICT DO NOTHING;
        """
    )


def downgrade() -> None:
    op.execute("DELETE FROM categories WHERE id IN (1, 2, 3, 4, 5);")

