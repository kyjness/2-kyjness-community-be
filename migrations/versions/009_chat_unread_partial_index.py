"""chat_messages: 미읽음 카운트용 부분 인덱스

Revision ID: 009_chat_unread_partial_index
Revises: 008_dog_representative_unique
Create Date: 2026-07-05 13:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "009_chat_unread_partial_index"
down_revision: str | None = "008_dog_representative_unique"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 인박스 미읽음 카운트는 방별 미읽음(is_read=false) 소수 행만 필요하다.
    # 부분 인덱스로 읽음 메시지를 배제해 방 전체 스캔 대신 미읽음만 도는 인덱스 스캔이 되게 한다.
    op.create_index(
        "ix_chat_messages_unread",
        "chat_messages",
        ["room_id"],
        postgresql_where=sa.text("is_read = false"),
    )


def downgrade() -> None:
    op.drop_index("ix_chat_messages_unread", table_name="chat_messages")
