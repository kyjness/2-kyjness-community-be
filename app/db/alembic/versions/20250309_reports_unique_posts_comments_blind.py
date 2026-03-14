"""reports 복합 유니크, posts/comments에 report_count·is_blinded 추가 (Phase 2)

Revision ID: reports_unique_blind
Revises: user_blocks_reports_role
Create Date: 2025-03-09

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "reports_unique_blind"
down_revision: str | None = "user_blocks_reports_role"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_unique_constraint(
        "uq_reports_reporter_target",
        "reports",
        ["reporter_id", "target_type", "target_id"],
    )

    op.add_column(
        "posts",
        sa.Column("report_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
    )
    op.add_column(
        "posts",
        sa.Column("is_blinded", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    )

    op.add_column(
        "comments",
        sa.Column("report_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
    )
    op.add_column(
        "comments",
        sa.Column("is_blinded", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    )


def downgrade() -> None:
    op.drop_column("comments", "is_blinded")
    op.drop_column("comments", "report_count")
    op.drop_column("posts", "is_blinded")
    op.drop_column("posts", "report_count")
    op.drop_constraint("uq_reports_reporter_target", "reports", type_="unique")
