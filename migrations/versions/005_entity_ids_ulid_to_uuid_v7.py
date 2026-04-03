"""ULID VARCHAR(26) → PostgreSQL uuid (기존 128비트 보존, 신규는 앱에서 UUID v7).

Revision ID: 005_ulid_to_uuid
Revises: 004_notifications
Create Date: 2026-04-03

- puppytalk_ulid_to_uuid(text): Crockford Base32 ULID 26자 → 동일 128비트 UUID (python-ulid와 동일 축).
- 모든 관련 FK를 잠시 제거한 뒤 컬럼을 uuid로 변환하고 FK를 복구한다.

-------------------------------------------------------------------------------
스모크 테스트 · 사전 검증 (스테이징 DB에서 upgrade 전에 실행)
-------------------------------------------------------------------------------

아래 쿼리로 실제 FK 이름이 이 스크립트의 _FK_TO_DROP 목록과 일치하는지 확인한다.
이름이 다르면(수동 DDL·다른 Alembic 리비전 등) 먼저 DB를 맞추거나, 목록을 환경에 맞게
수정한 전용 브랜치에서 마이그레이션을 실행한다. DROP은 IF EXISTS이므로 “이름만 다름”인
경우 제약이 남아 ALTER TYPE이 실패할 수 있다 — 사전 대조가 필수다.

-- (1) 이 마이그레이션이 건드리는 테이블에 달린 모든 외래키 이름·참조 관계
SELECT c.conname AS constraint_name,
       c.conrelid::regclass AS child_table,
       c.confrelid::regclass AS parent_table,
       pg_get_constraintdef(c.oid) AS definition
FROM pg_constraint c
JOIN pg_class r ON r.oid = c.conrelid
WHERE c.contype = 'f'
  AND r.relname IN (
    'users', 'images', 'posts', 'post_hashtags', 'dog_profiles',
    'post_images', 'post_likes', 'comments', 'comment_likes',
    'user_blocks', 'reports', 'notifications'
  )
ORDER BY r.relname::text, c.conname;

-- (2) 스크립트가 기대하는 이름이 전부 존재하는지(행이 비면 해당 이름은 DB에 없음)
SELECT c.conname, c.conrelid::regclass AS on_table
FROM pg_constraint c
WHERE c.contype = 'f'
  AND c.conname IN (
    'fk_users_profile_image',
    'images_uploader_id_fkey',
    'posts_user_id_fkey',
    'post_hashtags_post_id_fkey',
    'dog_profiles_owner_id_fkey',
    'dog_profiles_profile_image_id_fkey',
    'post_images_post_id_fkey',
    'post_images_image_id_fkey',
    'post_likes_post_id_fkey',
    'post_likes_user_id_fkey',
    'comments_post_id_fkey',
    'comments_author_id_fkey',
    'comments_parent_id_fkey',
    'comment_likes_comment_id_fkey',
    'comment_likes_user_id_fkey',
    'user_blocks_blocker_id_fkey',
    'user_blocks_blocked_id_fkey',
    'reports_reporter_id_fkey',
    'notifications_user_id_fkey',
    'notifications_actor_id_fkey',
    'notifications_post_id_fkey',
    'notifications_comment_id_fkey'
  )
ORDER BY c.conrelid::regclass::text, c.conname;

-------------------------------------------------------------------------------
운영 팁 · 락/타임아웃 (대용량 ALTER 완화)
-------------------------------------------------------------------------------

- ALTER TABLE ... ALTER COLUMN TYPE 은 ACCESS EXCLUSIVE 락을 오래 잡을 수 있다.
- psql(또는 마이그레이션 전용 역할 세션)에서 상한을 두면 무한 대기·장시간 점유를 줄인다.

  SET lock_timeout = '5s';       -- 락 획득 실패 시 빠르게 실패 → 창구 재시도
  SET statement_timeout = '1h';  -- 환경에 맞게 조정; 너무 짧으면 중도 실패

- 장애 조치: timeout으로 중단된 뒤 재실행은 **컬럼 타입이 이미 uuid인 테이블**에서
  ALTER가 다시 실패할 수 있으므로, `alembic_version`과 실제 컬럼 타입을 함께 확인한 뒤
  수동 복구 또는 맞춤 스크립트가 필요할 수 있다.

- 수천만 행 이상이면 “신규 uuid 컬럼 + 백필 + 스왑” 등 청크 전략을 별도 설계한다.

배포 후 Redis:
- refresh 토큰 키는 `user_refresh:{UUID}` 로 정규화되어 기존 ULID 키와 호환되지 않는다.
  사용자는 재로그인이 필요할 수 있다.
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "005_ulid_to_uuid"
down_revision: str | None = "004_notifications"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


_ULID_TO_UUID_FUNC = """
CREATE OR REPLACE FUNCTION puppytalk_ulid_to_uuid(s text)
RETURNS uuid AS $$
DECLARE
  acc numeric := 0;
  work numeric;
  i int;
  j int;
  c text;
  idx int;
  d int;
  alph constant text := '0123456789ABCDEFGHJKMNPQRSTVWXYZ';
  full_hex text := '';
BEGIN
  IF s IS NULL OR length(s) <> 26 THEN
    RAISE EXCEPTION 'invalid ulid length';
  END IF;
  FOR i IN 1..26 LOOP
    c := upper(substr(s, i, 1));
    idx := strpos(alph, c);
    IF idx = 0 THEN
      RAISE EXCEPTION 'invalid ulid char %', c;
    END IF;
    acc := acc * 32 + (idx - 1);
  END LOOP;
  -- 128비트만 사용(26×5=130비트 인코딩과 동일 축).
  work := acc % power(2::numeric, 128);
  -- 무부호 64비트 half는 PG bigint(부호)에 안 들어갈 수 있음 → 누블 단위로 hex 조립.
  FOR j IN 1..32 LOOP
    d := (work % 16)::int;
    full_hex := substr('0123456789abcdef', d + 1, 1) || full_hex;
    work := trunc(work / 16);
  END LOOP;
  RETURN (
    substring(full_hex from 1 for 8) || '-' ||
    substring(full_hex from 9 for 4) || '-' ||
    substring(full_hex from 13 for 4) || '-' ||
    substring(full_hex from 17 for 4) || '-' ||
    substring(full_hex from 21 for 12)
  )::uuid;
END;
$$ LANGUAGE plpgsql IMMUTABLE STRICT;
"""

# (table_name, constraint_name) — 사전 검증 쿼리(모듈 docstring)와 반드시 동기화할 것.
_FK_TO_DROP: list[tuple[str, str]] = [
    ("users", "fk_users_profile_image"),
    ("images", "images_uploader_id_fkey"),
    ("posts", "posts_user_id_fkey"),
    ("post_hashtags", "post_hashtags_post_id_fkey"),
    ("dog_profiles", "dog_profiles_owner_id_fkey"),
    ("dog_profiles", "dog_profiles_profile_image_id_fkey"),
    ("post_images", "post_images_post_id_fkey"),
    ("post_images", "post_images_image_id_fkey"),
    ("post_likes", "post_likes_post_id_fkey"),
    ("post_likes", "post_likes_user_id_fkey"),
    ("comments", "comments_post_id_fkey"),
    ("comments", "comments_author_id_fkey"),
    ("comments", "comments_parent_id_fkey"),
    ("comment_likes", "comment_likes_comment_id_fkey"),
    ("comment_likes", "comment_likes_user_id_fkey"),
    ("user_blocks", "user_blocks_blocker_id_fkey"),
    ("user_blocks", "user_blocks_blocked_id_fkey"),
    ("reports", "reports_reporter_id_fkey"),
    ("notifications", "notifications_user_id_fkey"),
    ("notifications", "notifications_actor_id_fkey"),
    ("notifications", "notifications_post_id_fkey"),
    ("notifications", "notifications_comment_id_fkey"),
]


def upgrade() -> None:
    op.execute(_ULID_TO_UUID_FUNC)
    conv = "puppytalk_ulid_to_uuid(CAST({col} AS text))"

    # DROP CONSTRAINT IF EXISTS: 이미 제거된 제약·재시도 시에도 크래시 완화.
    # 이름 불일치 시 제약이 남아 ALTER가 실패할 수 있으므로 docstring의 사전 검증 쿼리 필수.
    for table, cname in _FK_TO_DROP:
        op.execute(f"ALTER TABLE {table} DROP CONSTRAINT IF EXISTS {cname}")

    # --- Alter columns ---
    op.execute(f"ALTER TABLE users ALTER COLUMN id TYPE uuid USING {conv.format(col='id')}")
    op.execute(
        f"ALTER TABLE users ALTER COLUMN profile_image_id TYPE uuid USING "
        f"CASE WHEN profile_image_id IS NULL THEN NULL ELSE {conv.format(col='profile_image_id')} END"
    )

    op.execute(f"ALTER TABLE images ALTER COLUMN id TYPE uuid USING {conv.format(col='id')}")
    op.execute(
        f"ALTER TABLE images ALTER COLUMN uploader_id TYPE uuid USING "
        f"CASE WHEN uploader_id IS NULL THEN NULL ELSE {conv.format(col='uploader_id')} END"
    )

    op.execute(f"ALTER TABLE posts ALTER COLUMN id TYPE uuid USING {conv.format(col='id')}")
    op.execute(
        f"ALTER TABLE posts ALTER COLUMN user_id TYPE uuid USING "
        f"CASE WHEN user_id IS NULL THEN NULL ELSE {conv.format(col='user_id')} END"
    )

    op.execute(
        f"ALTER TABLE post_hashtags ALTER COLUMN post_id TYPE uuid USING {conv.format(col='post_id')}"
    )

    op.execute(f"ALTER TABLE dog_profiles ALTER COLUMN id TYPE uuid USING {conv.format(col='id')}")
    op.execute(
        f"ALTER TABLE dog_profiles ALTER COLUMN owner_id TYPE uuid USING {conv.format(col='owner_id')}"
    )
    op.execute(
        f"ALTER TABLE dog_profiles ALTER COLUMN profile_image_id TYPE uuid USING "
        f"CASE WHEN profile_image_id IS NULL THEN NULL ELSE {conv.format(col='profile_image_id')} END"
    )

    op.execute(f"ALTER TABLE post_images ALTER COLUMN id TYPE uuid USING {conv.format(col='id')}")
    op.execute(
        f"ALTER TABLE post_images ALTER COLUMN post_id TYPE uuid USING {conv.format(col='post_id')}"
    )
    op.execute(
        f"ALTER TABLE post_images ALTER COLUMN image_id TYPE uuid USING {conv.format(col='image_id')}"
    )

    op.execute(
        f"ALTER TABLE post_likes ALTER COLUMN post_id TYPE uuid USING {conv.format(col='post_id')}"
    )
    op.execute(
        f"ALTER TABLE post_likes ALTER COLUMN user_id TYPE uuid USING {conv.format(col='user_id')}"
    )

    op.execute(f"ALTER TABLE comments ALTER COLUMN id TYPE uuid USING {conv.format(col='id')}")
    op.execute(
        f"ALTER TABLE comments ALTER COLUMN post_id TYPE uuid USING {conv.format(col='post_id')}"
    )
    op.execute(
        f"ALTER TABLE comments ALTER COLUMN author_id TYPE uuid USING "
        f"CASE WHEN author_id IS NULL THEN NULL ELSE {conv.format(col='author_id')} END"
    )
    op.execute(
        f"ALTER TABLE comments ALTER COLUMN parent_id TYPE uuid USING "
        f"CASE WHEN parent_id IS NULL THEN NULL ELSE {conv.format(col='parent_id')} END"
    )

    op.execute(
        f"ALTER TABLE comment_likes ALTER COLUMN comment_id TYPE uuid USING {conv.format(col='comment_id')}"
    )
    op.execute(
        f"ALTER TABLE comment_likes ALTER COLUMN user_id TYPE uuid USING {conv.format(col='user_id')}"
    )

    op.execute(
        f"ALTER TABLE user_blocks ALTER COLUMN blocker_id TYPE uuid USING {conv.format(col='blocker_id')}"
    )
    op.execute(
        f"ALTER TABLE user_blocks ALTER COLUMN blocked_id TYPE uuid USING {conv.format(col='blocked_id')}"
    )

    op.execute(f"ALTER TABLE reports ALTER COLUMN id TYPE uuid USING {conv.format(col='id')}")
    op.execute(
        f"ALTER TABLE reports ALTER COLUMN reporter_id TYPE uuid USING {conv.format(col='reporter_id')}"
    )
    op.execute(
        f"ALTER TABLE reports ALTER COLUMN target_id TYPE uuid USING {conv.format(col='target_id')}"
    )

    op.execute(f"ALTER TABLE notifications ALTER COLUMN id TYPE uuid USING {conv.format(col='id')}")
    op.execute(
        f"ALTER TABLE notifications ALTER COLUMN user_id TYPE uuid USING {conv.format(col='user_id')}"
    )
    op.execute(
        f"ALTER TABLE notifications ALTER COLUMN actor_id TYPE uuid USING "
        f"CASE WHEN actor_id IS NULL THEN NULL ELSE {conv.format(col='actor_id')} END"
    )
    op.execute(
        f"ALTER TABLE notifications ALTER COLUMN post_id TYPE uuid USING "
        f"CASE WHEN post_id IS NULL THEN NULL ELSE {conv.format(col='post_id')} END"
    )
    op.execute(
        f"ALTER TABLE notifications ALTER COLUMN comment_id TYPE uuid USING "
        f"CASE WHEN comment_id IS NULL THEN NULL ELSE {conv.format(col='comment_id')} END"
    )

    # --- Recreate FKs (001 + 004와 동일 ondelete) ---
    op.create_foreign_key(
        "fk_users_profile_image",
        "users",
        "images",
        ["profile_image_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_foreign_key(
        "images_uploader_id_fkey",
        "images",
        "users",
        ["uploader_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_foreign_key(
        "posts_user_id_fkey",
        "posts",
        "users",
        ["user_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_foreign_key(
        "post_hashtags_post_id_fkey",
        "post_hashtags",
        "posts",
        ["post_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_foreign_key(
        "dog_profiles_owner_id_fkey",
        "dog_profiles",
        "users",
        ["owner_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_foreign_key(
        "dog_profiles_profile_image_id_fkey",
        "dog_profiles",
        "images",
        ["profile_image_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_foreign_key(
        "post_images_post_id_fkey",
        "post_images",
        "posts",
        ["post_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_foreign_key(
        "post_images_image_id_fkey",
        "post_images",
        "images",
        ["image_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_foreign_key(
        "post_likes_post_id_fkey",
        "post_likes",
        "posts",
        ["post_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_foreign_key(
        "post_likes_user_id_fkey",
        "post_likes",
        "users",
        ["user_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_foreign_key(
        "comments_post_id_fkey",
        "comments",
        "posts",
        ["post_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_foreign_key(
        "comments_author_id_fkey",
        "comments",
        "users",
        ["author_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_foreign_key(
        "comments_parent_id_fkey",
        "comments",
        "comments",
        ["parent_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_foreign_key(
        "comment_likes_comment_id_fkey",
        "comment_likes",
        "comments",
        ["comment_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_foreign_key(
        "comment_likes_user_id_fkey",
        "comment_likes",
        "users",
        ["user_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_foreign_key(
        "user_blocks_blocker_id_fkey",
        "user_blocks",
        "users",
        ["blocker_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_foreign_key(
        "user_blocks_blocked_id_fkey",
        "user_blocks",
        "users",
        ["blocked_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_foreign_key(
        "reports_reporter_id_fkey",
        "reports",
        "users",
        ["reporter_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_foreign_key(
        "notifications_user_id_fkey",
        "notifications",
        "users",
        ["user_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_foreign_key(
        "notifications_actor_id_fkey",
        "notifications",
        "users",
        ["actor_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_foreign_key(
        "notifications_post_id_fkey",
        "notifications",
        "posts",
        ["post_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_foreign_key(
        "notifications_comment_id_fkey",
        "notifications",
        "comments",
        ["comment_id"],
        ["id"],
        ondelete="CASCADE",
    )

    op.execute("DROP FUNCTION IF EXISTS puppytalk_ulid_to_uuid(text)")


def downgrade() -> None:
    raise NotImplementedError("uuid → ulid 문자열 복원은 손실·비결정적이므로 지원하지 않습니다.")
