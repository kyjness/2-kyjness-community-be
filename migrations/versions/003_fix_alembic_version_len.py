"""Widen alembic_version.version_num for long revision IDs.

Revision ID: 003_fix_alembic_version_len
Revises: 002_seed_categories
Create Date: 2026-03-26
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "003_fix_alembic_version_len"
down_revision: str | None = "002_seed_categories"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Alembic 기본 alembic_version.version_num은 VARCHAR(32)라 긴 revision id에서 실패할 수 있음.
    op.alter_column(
        "alembic_version",
        "version_num",
        existing_type=sa.String(length=32),
        type_=sa.String(length=255),
        existing_nullable=False,
    )


def downgrade() -> None:
    op.alter_column(
        "alembic_version",
        "version_num",
        existing_type=sa.String(length=255),
        type_=sa.String(length=32),
        existing_nullable=False,
    )
