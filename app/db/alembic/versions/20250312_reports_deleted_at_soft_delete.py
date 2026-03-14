"""reports deleted_at 추가, 유니크 제거(동일 유저 재신고 허용)

Revision ID: reports_deleted_at
Revises: b4929405b32f
Create Date: 2025-03-12

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "reports_deleted_at"
down_revision: str | None = "b4929405b32f"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_constraint("uq_reports_reporter_target", "reports", type_="unique")
    op.add_column(
        "reports",
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("reports", "deleted_at")
    op.create_unique_constraint(
        "uq_reports_reporter_target",
        "reports",
        ["reporter_id", "target_type", "target_id"],
    )
