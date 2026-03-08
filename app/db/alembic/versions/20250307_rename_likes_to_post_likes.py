"""likes 테이블을 post_likes로 이름 변경 (게시글 전용 좋아요)

Revision ID: rename_likes_post_likes
Revises: comments_parent_id
Create Date: 2025-03-07

"""

from typing import Sequence, Union

from alembic import op


revision: str = "rename_likes_post_likes"
down_revision: Union[str, None] = "comments_parent_id"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.rename_table("likes", "post_likes")


def downgrade() -> None:
    op.rename_table("post_likes", "likes")
