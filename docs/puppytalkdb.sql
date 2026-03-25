-- puppytalk DB 스키마 (PostgreSQL). 참고용 DDL.
-- 실제 스키마는 Alembic(001_initial_baseline)로 적용하는 것을 권장합니다.
--
-- 사용(참고용): psql -U postgres -d puppytalk -f docs/puppytalkdb.sql
-- 사용(권장): alembic upgrade head

CREATE EXTENSION IF NOT EXISTS pg_trgm;

DROP TABLE IF EXISTS reports;
DROP TABLE IF EXISTS user_blocks;
DROP TABLE IF EXISTS comment_likes;
DROP TABLE IF EXISTS comments;
DROP TABLE IF EXISTS post_likes;
DROP TABLE IF EXISTS post_images;
DROP TABLE IF EXISTS dog_profiles;
DROP TABLE IF EXISTS post_hashtags;
DROP TABLE IF EXISTS posts;
DROP TABLE IF EXISTS hashtags;
DROP TABLE IF EXISTS categories;
DROP TABLE IF EXISTS images;
DROP TABLE IF EXISTS users;

-- users
CREATE TABLE users (
    id                  SERIAL PRIMARY KEY,
    version             INTEGER NOT NULL DEFAULT 1,
    email               VARCHAR(255) NOT NULL UNIQUE,
    password            VARCHAR(255) NOT NULL,
    nickname            VARCHAR(255) NOT NULL UNIQUE,
    profile_image_id    INTEGER NULL,
    role                VARCHAR(20) NOT NULL DEFAULT 'USER',
    status              VARCHAR(20) NOT NULL DEFAULT 'ACTIVE',
    created_at          TIMESTAMPTZ NOT NULL,
    updated_at          TIMESTAMPTZ NOT NULL,
    deleted_at          TIMESTAMPTZ NULL
);

-- images
CREATE TABLE images (
    id              SERIAL PRIMARY KEY,
    file_key        VARCHAR(255) NOT NULL,
    file_url        VARCHAR(999) NOT NULL,
    content_type    VARCHAR(255) NULL,
    size            INTEGER NULL,
    uploader_id     INTEGER NULL,
    created_at      TIMESTAMPTZ NOT NULL,
    CONSTRAINT fk_images_uploader FOREIGN KEY (uploader_id) REFERENCES users(id) ON DELETE SET NULL
);
CREATE INDEX idx_images_uploader_id ON images(uploader_id);

ALTER TABLE users
  ADD CONSTRAINT fk_users_profile_image
  FOREIGN KEY (profile_image_id) REFERENCES images(id) ON DELETE SET NULL;

-- categories / hashtags
CREATE TABLE categories (
    id          SERIAL PRIMARY KEY,
    name        VARCHAR(50) NOT NULL UNIQUE,
    description TEXT NULL
);
CREATE INDEX idx_categories_name ON categories(name);

CREATE TABLE hashtags (
    id      SERIAL PRIMARY KEY,
    name    VARCHAR(50) NOT NULL UNIQUE
);
CREATE INDEX idx_hashtags_name ON hashtags(name);

-- posts
CREATE TABLE posts (
    id              SERIAL PRIMARY KEY,
    user_id         INTEGER NOT NULL,
    title           VARCHAR(255) NOT NULL,
    content         TEXT NOT NULL,
    category_id     INTEGER NULL,
    view_count      INTEGER NOT NULL DEFAULT 0,
    like_count      INTEGER NOT NULL DEFAULT 0,
    comment_count   INTEGER NOT NULL DEFAULT 0,
    report_count    INTEGER NOT NULL DEFAULT 0,
    is_blinded      BOOLEAN NOT NULL DEFAULT FALSE,
    created_at      TIMESTAMPTZ NOT NULL,
    updated_at      TIMESTAMPTZ NOT NULL,
    deleted_at      TIMESTAMPTZ NULL,
    version         INTEGER NOT NULL DEFAULT 1,
    CONSTRAINT fk_posts_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    CONSTRAINT fk_posts_category FOREIGN KEY (category_id) REFERENCES categories(id) ON DELETE SET NULL
);
CREATE INDEX idx_posts_user_id ON posts(user_id);
CREATE INDEX idx_posts_category_id ON posts(category_id);
CREATE INDEX idx_posts_deleted_at_id ON posts(deleted_at, id);
CREATE INDEX idx_posts_title_gin ON posts USING gin (title gin_trgm_ops);
CREATE INDEX idx_posts_content_gin ON posts USING gin (content gin_trgm_ops);

-- post_hashtags (M:N)
CREATE TABLE post_hashtags (
    post_id     INTEGER NOT NULL,
    hashtag_id  INTEGER NOT NULL,
    PRIMARY KEY (post_id, hashtag_id),
    CONSTRAINT fk_post_hashtags_post FOREIGN KEY (post_id) REFERENCES posts(id) ON DELETE CASCADE,
    CONSTRAINT fk_post_hashtags_hashtag FOREIGN KEY (hashtag_id) REFERENCES hashtags(id) ON DELETE CASCADE
);

-- dog_profiles
CREATE TABLE dog_profiles (
    id                  SERIAL PRIMARY KEY,
    owner_id            INTEGER NOT NULL,
    name                VARCHAR(100) NOT NULL,
    breed               VARCHAR(100) NOT NULL,
    gender              VARCHAR(20) NOT NULL,
    birth_date          DATE NOT NULL,
    profile_image_id    INTEGER NULL,
    is_representative   BOOLEAN NOT NULL DEFAULT FALSE,
    created_at          TIMESTAMPTZ NOT NULL,
    updated_at          TIMESTAMPTZ NOT NULL,
    CONSTRAINT fk_dog_profiles_owner FOREIGN KEY (owner_id) REFERENCES users(id) ON DELETE CASCADE,
    CONSTRAINT fk_dog_profiles_profile_image FOREIGN KEY (profile_image_id) REFERENCES images(id) ON DELETE SET NULL
);
CREATE INDEX idx_dog_profiles_owner_id ON dog_profiles(owner_id);
CREATE INDEX idx_dog_profiles_profile_image_id ON dog_profiles(profile_image_id);

-- post_images
CREATE TABLE post_images (
    id          SERIAL PRIMARY KEY,
    post_id     INTEGER NOT NULL,
    image_id    INTEGER NOT NULL,
    created_at  TIMESTAMPTZ NOT NULL,
    CONSTRAINT fk_post_images_post FOREIGN KEY (post_id) REFERENCES posts(id) ON DELETE RESTRICT,
    CONSTRAINT fk_post_images_image FOREIGN KEY (image_id) REFERENCES images(id) ON DELETE CASCADE,
    CONSTRAINT uq_post_images_image_id UNIQUE (image_id)
);
CREATE INDEX idx_post_images_post_id ON post_images(post_id);
CREATE INDEX idx_post_images_image_id ON post_images(image_id);

-- post_likes
CREATE TABLE post_likes (
    post_id     INTEGER NOT NULL,
    user_id     INTEGER NOT NULL,
    created_at  TIMESTAMPTZ NOT NULL,
    PRIMARY KEY (post_id, user_id),
    CONSTRAINT fk_post_likes_post FOREIGN KEY (post_id) REFERENCES posts(id) ON DELETE CASCADE,
    CONSTRAINT fk_post_likes_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

-- comments
CREATE TABLE comments (
    id          SERIAL PRIMARY KEY,
    post_id     INTEGER NOT NULL,
    author_id   INTEGER NOT NULL,
    parent_id   INTEGER NULL,
    content     TEXT NOT NULL,
    like_count  INTEGER NOT NULL DEFAULT 0,
    report_count INTEGER NOT NULL DEFAULT 0,
    is_blinded  BOOLEAN NOT NULL DEFAULT FALSE,
    created_at  TIMESTAMPTZ NOT NULL,
    updated_at  TIMESTAMPTZ NOT NULL,
    deleted_at  TIMESTAMPTZ NULL,
    CONSTRAINT fk_comments_post FOREIGN KEY (post_id) REFERENCES posts(id) ON DELETE CASCADE,
    CONSTRAINT fk_comments_author FOREIGN KEY (author_id) REFERENCES users(id) ON DELETE CASCADE,
    CONSTRAINT fk_comments_parent FOREIGN KEY (parent_id) REFERENCES comments(id) ON DELETE CASCADE
);
CREATE INDEX idx_comments_post_id ON comments(post_id);
CREATE INDEX idx_comments_author_id ON comments(author_id);
CREATE INDEX idx_comments_parent_id ON comments(parent_id);

-- comment_likes
CREATE TABLE comment_likes (
    comment_id  INTEGER NOT NULL,
    user_id     INTEGER NOT NULL,
    created_at  TIMESTAMPTZ NOT NULL,
    PRIMARY KEY (comment_id, user_id),
    CONSTRAINT fk_comment_likes_comment FOREIGN KEY (comment_id) REFERENCES comments(id) ON DELETE CASCADE,
    CONSTRAINT fk_comment_likes_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

-- user_blocks
CREATE TABLE user_blocks (
    blocker_id  INTEGER NOT NULL,
    blocked_id  INTEGER NOT NULL,
    created_at  TIMESTAMPTZ NOT NULL,
    PRIMARY KEY (blocker_id, blocked_id),
    CONSTRAINT uq_user_blocks_blocker_blocked UNIQUE (blocker_id, blocked_id),
    CONSTRAINT fk_user_blocks_blocker FOREIGN KEY (blocker_id) REFERENCES users(id) ON DELETE CASCADE,
    CONSTRAINT fk_user_blocks_blocked FOREIGN KEY (blocked_id) REFERENCES users(id) ON DELETE CASCADE
);

-- reports
CREATE TABLE reports (
    id          SERIAL PRIMARY KEY,
    reporter_id INTEGER NOT NULL,
    target_type VARCHAR(50) NOT NULL,
    target_id   INTEGER NOT NULL,
    reason      TEXT NULL,
    created_at  TIMESTAMPTZ NOT NULL,
    deleted_at  TIMESTAMPTZ NULL,
    CONSTRAINT fk_reports_reporter FOREIGN KEY (reporter_id) REFERENCES users(id) ON DELETE CASCADE
);
CREATE INDEX idx_reports_reporter_id ON reports(reporter_id);
