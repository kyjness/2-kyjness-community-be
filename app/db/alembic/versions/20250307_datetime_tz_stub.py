"""Stub for missing revision datetime_tz (DB에만 있는 리비전 복구용 no-op)

Revision ID: datetime_tz
Revises: add_comment_likes
Create Date: 2025-03-07

- 이전에 적용된 datetime_tz 마이그레이션 파일이 제거되어, DB의 alembic_version이
  datetime_tz를 가리킬 때 'Can't locate revision' 오류가 발생함.
- 이 파일은 해당 리비전을 복구하여 체인을 이어주며, upgrade/downgrade는 no-op.
"""

from collections.abc import Sequence

revision: str = "datetime_tz"
down_revision: str | None = "add_comment_likes"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
