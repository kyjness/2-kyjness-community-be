"""users is_active -> status (UserStatus enum) 전환

Revision ID: user_status
Revises: add_dog_profiles
Create Date: 2025-03-05

- status 컬럼 추가 후 기존 is_active 값으로 데이터 이전, is_active 삭제.
- is_active=True/False 모두 ACTIVE로 매핑 (PENDING 미사용).
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "user_status"
down_revision: Union[str, None] = "add_dog_profiles"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1) status 컬럼 추가 (NOT NULL, 기본값 ACTIVE)
    op.add_column(
        "users",
        sa.Column("status", sa.String(20), nullable=False, server_default=sa.text("'ACTIVE'")),
    )
    # 2) 기존 is_active 값으로 status 설정 (True/False 모두 ACTIVE)
    op.execute("UPDATE users SET status = 'ACTIVE'")
    # 3) is_active 컬럼 삭제
    op.drop_column("users", "is_active")
    # (선택) status로 필터링하는 쿼리가 많아지면: op.create_index(op.f("ix_users_status"), "users", ["status"], unique=False)


def downgrade() -> None:
    op.add_column(
        "users",
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
    )
    op.execute("UPDATE users SET is_active = IF(status = 'ACTIVE', 1, 0)")
    op.drop_column("users", "status")
