"""add dog_profiles table (User 1:N, MySQL 3780 방지용 FK 타입 일치)

Revision ID: add_dog_profiles
Revises: drop_sessions
Create Date: 2025-03-05

- owner_id, profile_image_id: users.id / images.id가 INT UNSIGNED일 때 동일 타입 사용.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.mysql import INTEGER


revision: str = "add_dog_profiles"
down_revision: Union[str, None] = "drop_sessions"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # MySQL 3780: FK 컬럼은 참조 컬럼과 동일 타입·부호여야 함. INT UNSIGNED 사용.
    op.create_table(
        "dog_profiles",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("owner_id", INTEGER(unsigned=True), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("breed", sa.String(100), nullable=False),
        sa.Column("gender", sa.String(20), nullable=False),
        sa.Column("birth_date", sa.Date(), nullable=False),
        sa.Column("profile_image_id", INTEGER(unsigned=True), nullable=True),
        sa.Column("is_representative", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["owner_id"],
            ["users.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["profile_image_id"],
            ["images.id"],
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_dog_profiles_owner_id"), "dog_profiles", ["owner_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_dog_profiles_owner_id"), table_name="dog_profiles")
    op.drop_table("dog_profiles")
