"""dog_profiles: 소유자당 대표견 1마리 부분 유니크 인덱스

Revision ID: 008_dog_representative_unique
Revises: 007_pg_trgm_search
Create Date: 2026-07-05 12:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "008_dog_representative_unique"
down_revision: str | None = "007_pg_trgm_search"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 유니크 인덱스 생성 전, 기존 데이터에 소유자당 대표견이 2개 이상 있으면 생성이 실패한다.
    # 소유자별로 가장 이른(uuidv7는 시간정렬이라 MIN=최초 지정) 대표견 1개만 남기고 해제한다.
    op.execute(
        sa.text(
            """
            UPDATE dog_profiles
            SET is_representative = false
            WHERE is_representative = true
              AND id <> (
                SELECT MIN(d2.id)
                FROM dog_profiles d2
                WHERE d2.owner_id = dog_profiles.owner_id
                  AND d2.is_representative = true
              )
            """
        )
    )
    op.create_index(
        "uq_dog_profiles_owner_representative",
        "dog_profiles",
        ["owner_id"],
        unique=True,
        postgresql_where=sa.text("is_representative"),
    )


def downgrade() -> None:
    op.drop_index("uq_dog_profiles_owner_representative", table_name="dog_profiles")
