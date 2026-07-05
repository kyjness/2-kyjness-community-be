"""reports: (target_type, target_id) 부분 인덱스

Revision ID: 011_reports_target_index
Revises: 010_notification_unread_index
Create Date: 2026-07-05 15:00:00.000000

관리자 신고 집계(bulk_max_created_at·bulk_reasons)와 delete_by_target가 모두
WHERE target_type AND target_id (AND deleted_at IS NULL)로 조회하는데 이 두 컬럼에
인덱스가 없어 테이블 스캔이었다. 모든 read 경로가 미삭제만 보므로 부분 인덱스로
살아있는 신고만 커버한다.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "011_reports_target_index"
down_revision: str | None = "010_notification_unread_index"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_index(
        "ix_reports_target",
        "reports",
        ["target_type", "target_id"],
        postgresql_where=sa.text("deleted_at IS NULL"),
    )


def downgrade() -> None:
    op.drop_index("ix_reports_target", table_name="reports")
