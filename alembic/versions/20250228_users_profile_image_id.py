"""users profile_image_url -> profile_image_id (FK images)

Revision ID: 20250228_users_fk
Revises:
Create Date: 2025-02-28

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "20250228_users_fk"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_column("users", "profile_image_url")
    op.add_column("users", sa.Column("profile_image_id", sa.Integer(), nullable=True))
    op.create_foreign_key(
        "fk_users_profile_image",
        "users",
        "images",
        ["profile_image_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint("fk_users_profile_image", "users", type_="foreignkey")
    op.drop_column("users", "profile_image_id")
    op.add_column("users", sa.Column("profile_image_url", sa.String(999), nullable=True))
