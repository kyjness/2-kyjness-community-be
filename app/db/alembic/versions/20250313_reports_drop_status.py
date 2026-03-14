"""reports.status 컬럼 제거 (미사용, 운영 워크플로우 단순화)

Revision ID: reports_drop_status
Revises: reports_deleted_at
Create Date: 2025-03-13

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "reports_drop_status"
down_revision: str | None = "reports_deleted_at"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_column("reports", "status")


def downgrade() -> None:
    op.add_column(
        "reports",
        sa.Column("status", sa.String(20), nullable=False, server_default=sa.text("'PENDING'")),
    )
