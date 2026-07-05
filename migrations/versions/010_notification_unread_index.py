"""notifications: 전체 읽음 처리용 부분 인덱스

Revision ID: 010_notification_unread_index
Revises: 009_chat_unread_partial_index
Create Date: 2026-07-05 14:00:00.000000

목록 keyset(ORDER BY created_at DESC, id DESC)은 004에서 만든
ix_notifications_user_created(user_id, created_at DESC)가 이미 커버한다. 여기서는
전체 읽음 처리(WHERE user_id AND read_at IS NULL)용 부분 인덱스만 추가한다.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "010_notification_unread_index"
down_revision: str | None = "009_chat_unread_partial_index"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_index(
        "ix_notifications_user_unread",
        "notifications",
        ["user_id"],
        postgresql_where=sa.text("read_at IS NULL"),
    )


def downgrade() -> None:
    op.drop_index("ix_notifications_user_unread", table_name="notifications")
