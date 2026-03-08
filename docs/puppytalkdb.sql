-- puppytalk DB 스키마 (PostgreSQL). 참고용 DDL. 실제 스키마는 Alembic 마이그레이션으로 적용.
-- 사용: psql -U postgres -d puppytalk -f docs/puppytalkdb.sql (또는 DB 생성 후 마이그레이션 권장: alembic upgrade head)

-- DB 생성은 마이그레이션 전에 수동으로: createdb -U postgres puppytalk

DROP TABLE IF EXISTS likes;
DROP TABLE IF EXISTS post_images;
DROP TABLE IF EXISTS comments;
DROP TABLE IF EXISTS posts;
DROP TABLE IF EXISTS dog_profiles;
DROP TABLE IF EXISTS images;
DROP TABLE IF EXISTS users;

-- users (탈퇴 시 애플리케이션 단에서 email/nickname에 suffix를 추가하여 UNIQUE 충돌 방지. status: UserStatus enum ACTIVE 등)
CREATE TABLE users (
    id                  SERIAL PRIMARY KEY,
    email               VARCHAR(255) NOT NULL UNIQUE,
    password            VARCHAR(255) NOT NULL,
    nickname            VARCHAR(255) NOT NULL UNIQUE,
    profile_image_id    INTEGER NULL,
    status              VARCHAR(20) NOT NULL DEFAULT 'ACTIVE',
    created_at          TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at          TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    deleted_at          TIMESTAMP NULL DEFAULT NULL
);

-- posts (카운트 필드 기본값 0)
CREATE TABLE posts (
    id              SERIAL PRIMARY KEY,
    user_id         INTEGER NOT NULL,
    title           VARCHAR(255) NOT NULL,
    content         TEXT NOT NULL,
    view_count      INTEGER NOT NULL DEFAULT 0,
    like_count      INTEGER NOT NULL DEFAULT 0,
    comment_count   INTEGER NOT NULL DEFAULT 0,
    created_at      TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at      TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    deleted_at      TIMESTAMP NULL DEFAULT NULL,

    CONSTRAINT fk_posts_user
      FOREIGN KEY (user_id) REFERENCES users(id)
      ON DELETE CASCADE
);

-- comments
CREATE TABLE comments (
    id          SERIAL PRIMARY KEY,
    post_id     INTEGER NOT NULL,
    author_id   INTEGER NOT NULL,
    content     TEXT NOT NULL,
    created_at  TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at  TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    deleted_at  TIMESTAMP NULL DEFAULT NULL,

    CONSTRAINT fk_comments_post
      FOREIGN KEY (post_id) REFERENCES posts(id)
      ON DELETE CASCADE,
    CONSTRAINT fk_comments_author
      FOREIGN KEY (author_id) REFERENCES users(id)
      ON DELETE CASCADE
);

-- images (프로필/게시글 업로드, post_images로 게시글 연결)
CREATE TABLE images (
    id                  SERIAL PRIMARY KEY,
    file_key            VARCHAR(255) NOT NULL,
    file_url            VARCHAR(999) NOT NULL,
    content_type        VARCHAR(255) NULL,
    size                INTEGER NULL,
    uploader_id         INTEGER NULL,
    ref_count           INTEGER NOT NULL DEFAULT 0,
    signup_token_hash   VARCHAR(64) NULL,
    signup_expires_at   TIMESTAMP NULL,
    created_at          TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT fk_images_uploader FOREIGN KEY (uploader_id) REFERENCES users(id) ON DELETE SET NULL
);

ALTER TABLE users
  ADD CONSTRAINT fk_users_profile_image
  FOREIGN KEY (profile_image_id) REFERENCES images(id) ON DELETE SET NULL;

-- dog_profiles (User 1:N, 대표 강아지 is_representative)
CREATE TABLE dog_profiles (
    id                  SERIAL PRIMARY KEY,
    owner_id            INTEGER NOT NULL,
    name                VARCHAR(100) NOT NULL,
    breed               VARCHAR(100) NOT NULL,
    gender              VARCHAR(20) NOT NULL,
    birth_date          DATE NOT NULL,
    profile_image_id    INTEGER NULL,
    is_representative   BOOLEAN NOT NULL DEFAULT FALSE,
    created_at          TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at          TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT fk_dog_profiles_owner
      FOREIGN KEY (owner_id) REFERENCES users(id) ON DELETE CASCADE,
    CONSTRAINT fk_dog_profiles_profile_image
      FOREIGN KEY (profile_image_id) REFERENCES images(id) ON DELETE SET NULL
);

-- post_images (게시글당 최대 5장. image_id UNIQUE로 한 이미지가 여러 포스트에 중복 등록 방지)
CREATE TABLE post_images (
    id          SERIAL PRIMARY KEY,
    post_id     INTEGER NOT NULL,
    image_id    INTEGER NOT NULL,
    created_at  TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT fk_post_images_post
      FOREIGN KEY (post_id) REFERENCES posts(id)
      ON DELETE RESTRICT,
    CONSTRAINT fk_post_images_image
      FOREIGN KEY (image_id) REFERENCES images(id)
      ON DELETE CASCADE,
    CONSTRAINT uq_post_images_image_id UNIQUE (image_id)
);

-- post_images: post당 최대 5개 제약 (애플리케이션에서도 검증 권장)
CREATE OR REPLACE FUNCTION check_post_images_max_five()
RETURNS TRIGGER AS $$
BEGIN
  IF (SELECT COUNT(*) FROM post_images WHERE post_id = NEW.post_id) >= 5 THEN
    RAISE EXCEPTION 'post_images: post당 최대 5개';
  END IF;
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS tr_post_images_max_five ON post_images;
CREATE TRIGGER tr_post_images_max_five
  BEFORE INSERT ON post_images
  FOR EACH ROW EXECUTE PROCEDURE check_post_images_max_five();

-- likes (게시글 Soft Delete 시 해당 post의 like 행은 물리 삭제. sessions 테이블 없음, JWT+Redis 전용)
CREATE TABLE likes (
    post_id     INTEGER NOT NULL,
    user_id     INTEGER NOT NULL,
    created_at  TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (post_id, user_id),

    CONSTRAINT fk_likes_post
      FOREIGN KEY (post_id) REFERENCES posts(id)
      ON DELETE CASCADE,
    CONSTRAINT fk_likes_user
      FOREIGN KEY (user_id) REFERENCES users(id)
      ON DELETE CASCADE
);

CREATE INDEX idx_posts_user_id ON posts(user_id);
CREATE INDEX idx_posts_deleted_at_id ON posts(deleted_at, id DESC);
CREATE INDEX idx_comments_post_id ON comments(post_id);
CREATE INDEX idx_comments_author_id ON comments(author_id);
CREATE INDEX idx_images_uploader_id ON images(uploader_id);
CREATE INDEX idx_images_signup_expires_at ON images(signup_expires_at);
CREATE INDEX idx_post_images_post_id ON post_images(post_id);
CREATE INDEX idx_post_images_image_id ON post_images(image_id);
CREATE INDEX idx_dog_profiles_owner_id ON dog_profiles(owner_id);
