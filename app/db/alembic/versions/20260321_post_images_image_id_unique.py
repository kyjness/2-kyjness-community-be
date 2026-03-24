"""post_images.image_id 유니크 제약 복구 (중복 행 선제 삭제)

Revision ID: post_images_image_id_unique
Revises: reports_drop_status
Create Date: 2026-03-21

- b4929405b32f에서 uq_post_images_image_id가 제거됨 → 동일 image_id가 여러 post에 매핑될 수 있었음.
- upgrade: image_id당 id가 가장 큰 행(가장 나중에 연결된 매핑)만 남기고 나머지 post_images 행 삭제 후 유니크 생성.
- 운영 반영 전 스테이징에서 반드시 중복 건수·삭제 영향 확인.

배포 전 점검 SQL(주석):
    SELECT image_id, COUNT(*) AS n
    FROM post_images
    GROUP BY image_id
    HAVING COUNT(*) > 1;

삭제 후 images.ref_count 등 앱 레벨 카운트와 불일치할 수 있으므로, 필요 시 별도 정합성 점검 스크립트 실행.
"""
from collections.abc import Sequence

from alembic import op
from sqlalchemy import text

revision: str = "post_images_image_id_unique"
down_revision: str | None = "reports_drop_status"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_UQ_NAME = "uq_post_images_image_id"


def upgrade() -> None:
    # 동일 image_id에 대해 id가 가장 큰 행만 유지 (최근 연결 우선).
    op.execute(
        text(
            """
            DELETE FROM post_images AS d
            WHERE EXISTS (
                SELECT 1 FROM post_images AS p
                WHERE p.image_id = d.image_id AND p.id > d.id
            )
            """
        )
    )
    op.create_unique_constraint(_UQ_NAME, "post_images", ["image_id"])


def downgrade() -> None:
    op.drop_constraint(_UQ_NAME, "post_images", type_="unique")
