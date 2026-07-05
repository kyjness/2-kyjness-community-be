"""notifications: keyset 목록 인덱스 정합 + 전체 읽음 부분 인덱스

Revision ID: 010_notification_unread_index
Revises: 009_chat_unread_partial_index
Create Date: 2026-07-05 14:00:00.000000

목록을 (id DESC) 단일 컬럼 keyset(comments와 동형)으로 전환하면서, 004의
ix_notifications_user_created(user_id, created_at DESC)를 정렬 축에 맞는
ix_notifications_user_recent(user_id, id DESC)로 교체한다. 더해 전체 읽음 처리
(WHERE user_id AND read_at IS NULL)용 부분 인덱스를 추가한다.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "010_notification_unread_index"
down_revision: str | None = "009_chat_unread_partial_index"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_index("ix_notifications_user_created", table_name="notifications")
    op.create_index(
        "ix_notifications_user_recent",
        "notifications",
        ["user_id", sa.text("id DESC")],
    )
    op.create_index(
        "ix_notifications_user_unread",
        "notifications",
        ["user_id"],
        postgresql_where=sa.text("read_at IS NULL"),
    )


def downgrade() -> None:
    op.drop_index("ix_notifications_user_unread", table_name="notifications")
    op.drop_index("ix_notifications_user_recent", table_name="notifications")
    op.create_index(
        "ix_notifications_user_created",
        "notifications",
        ["user_id", sa.text("created_at DESC")],
    )
