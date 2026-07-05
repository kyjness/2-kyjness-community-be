"""user_blocks: 복합 PK와 중복인 UNIQUE 제약 제거

Revision ID: 012_drop_redundant_user_block_unique
Revises: 011_reports_target_index
Create Date: 2026-07-05 16:00:00.000000

user_blocks는 (blocker_id, blocked_id) 복합 PK로 이미 유니크를 보장하는데, 동일 컬럼·순서의
UniqueConstraint(uq_user_blocks_blocker_blocked)가 또 있어 중복 유니크 인덱스를 만든다.
쓰기마다 두 유니크 인덱스를 갱신할 뿐 얻는 게 없으므로 제거한다. 복합 PK는 그대로 둔다.
"""

from collections.abc import Sequence

from alembic import op

revision: str = "012_drop_redundant_user_block_unique"
down_revision: str | None = "011_reports_target_index"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_constraint("uq_user_blocks_blocker_blocked", "user_blocks", type_="unique")


def downgrade() -> None:
    op.create_unique_constraint(
        "uq_user_blocks_blocker_blocked", "user_blocks", ["blocker_id", "blocked_id"]
    )
