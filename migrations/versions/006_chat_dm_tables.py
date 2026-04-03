"""1:1 DM chat_rooms, chat_messages (UUID v7 앱 기본값).

Revision ID: 006_chat_dm
Revises: 005_ulid_to_uuid
Create Date: 2026-04-03
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "006_chat_dm"
down_revision: str | None = "005_ulid_to_uuid"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_PG_UUID = postgresql.UUID(as_uuid=True)


def upgrade() -> None:
    op.create_table(
        "chat_rooms",
        sa.Column("id", _PG_UUID, nullable=False),
        sa.Column("user1_id", _PG_UUID, nullable=False),
        sa.Column("user2_id", _PG_UUID, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("user1_id < user2_id", name="ck_chat_rooms_user_order"),
        sa.ForeignKeyConstraint(["user1_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user2_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user1_id", "user2_id", name="uq_chat_rooms_user_pair"),
    )
    op.create_index("ix_chat_rooms_user1_id", "chat_rooms", ["user1_id"], unique=False)
    op.create_index("ix_chat_rooms_user2_id", "chat_rooms", ["user2_id"], unique=False)

    op.create_table(
        "chat_messages",
        sa.Column("id", _PG_UUID, nullable=False),
        sa.Column("room_id", _PG_UUID, nullable=False),
        sa.Column("sender_id", _PG_UUID, nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("is_read", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["room_id"], ["chat_rooms.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["sender_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_chat_messages_sender_id", "chat_messages", ["sender_id"], unique=False)
    op.create_index(
        "ix_chat_messages_room_created",
        "chat_messages",
        ["room_id", sa.text("created_at DESC")],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_chat_messages_room_created", table_name="chat_messages")
    op.drop_index("ix_chat_messages_sender_id", table_name="chat_messages")
    op.drop_table("chat_messages")
    op.drop_index("ix_chat_rooms_user2_id", table_name="chat_rooms")
    op.drop_index("ix_chat_rooms_user1_id", table_name="chat_rooms")
    op.drop_table("chat_rooms")
