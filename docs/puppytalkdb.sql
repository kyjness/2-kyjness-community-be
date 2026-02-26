-- puppytalk DB 스키마 (복붙 후 그대로 실행 가능, 재실행 시 기존 테이블 삭제 후 재생성)
-- 사용: mysql -u root -p < docs/puppytalkdb.sql  또는 클라이언트에서 전체 선택 후 실행

CREATE DATABASE IF NOT EXISTS puppytalk
  DEFAULT CHARACTER SET utf8mb4
  DEFAULT COLLATE utf8mb4_unicode_ci;

USE puppytalk;

-- 기존 테이블 제거 (FK 때문에 순서 무관하도록 체크 비활성화)
SET FOREIGN_KEY_CHECKS = 0;

DROP TABLE IF EXISTS likes;
DROP TABLE IF EXISTS post_images;
DROP TABLE IF EXISTS comments;
DROP TABLE IF EXISTS sessions;
DROP TABLE IF EXISTS posts;
DROP TABLE IF EXISTS images;
DROP TABLE IF EXISTS users;

SET FOREIGN_KEY_CHECKS = 1;

-- 1. users
CREATE TABLE users (
    id                  INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    email               VARCHAR(255) NOT NULL UNIQUE,
    password            VARCHAR(999) NOT NULL,
    nickname            VARCHAR(255) NOT NULL UNIQUE,
    profile_image_url   VARCHAR(999) NULL,
    created_at          TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at          TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    deleted_at          TIMESTAMP NULL DEFAULT NULL
);

-- 2. posts
CREATE TABLE posts (
    id              INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    user_id         INT UNSIGNED NOT NULL,
    title           VARCHAR(255) NOT NULL,
    content         TEXT NOT NULL,
    view_count      INT UNSIGNED NOT NULL DEFAULT 0,
    like_count      INT UNSIGNED NOT NULL DEFAULT 0,
    comment_count   INT UNSIGNED NOT NULL DEFAULT 0,
    created_at      TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at      TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    deleted_at      TIMESTAMP NULL DEFAULT NULL,

    CONSTRAINT fk_posts_user
      FOREIGN KEY (user_id) REFERENCES users(id)
      ON DELETE CASCADE
);

-- 3. comments
CREATE TABLE comments (
    id          INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    post_id     INT UNSIGNED NOT NULL,
    author_id   INT UNSIGNED NOT NULL,
    content     TEXT NOT NULL,
    created_at  TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at  TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    deleted_at  TIMESTAMP NULL DEFAULT NULL,

    CONSTRAINT fk_comments_post
      FOREIGN KEY (post_id) REFERENCES posts(id)
      ON DELETE CASCADE,
    CONSTRAINT fk_comments_author
      FOREIGN KEY (author_id) REFERENCES users(id)
      ON DELETE CASCADE
);

-- 4. 이미지 업로드 통합. 프로필/게시글 업로드 시 모두 이 테이블에 저장. 게시글 연결은 post_images로.
-- signup_token_hash/signup_expires_at: 회원가입 전 프로필 업로드용. attach 시 NULL로 초기화.
CREATE TABLE images (
    id                  INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    file_key            VARCHAR(255) NOT NULL COMMENT '저장 경로(profile/xxx.jpg 또는 post/xxx.jpg)',
    file_url            VARCHAR(999) NOT NULL COMMENT '공개 URL',
    content_type        VARCHAR(255) NULL,
    size                INT UNSIGNED NULL,
    uploader_id          INT UNSIGNED NULL COMMENT '업로더(비회원 가입 전이면 NULL)',
    signup_token_hash   VARCHAR(64) NULL COMMENT '회원가입용 토큰 해시. attach 시 NULL',
    signup_expires_at   TIMESTAMP NULL COMMENT '회원가입용 만료. attach 시 NULL',
    created_at          TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    deleted_at          TIMESTAMP NULL DEFAULT NULL,

    CONSTRAINT fk_images_uploader FOREIGN KEY (uploader_id) REFERENCES users(id) ON DELETE SET NULL
);

-- 5. post_images (게시글-이미지 연결 테이블)
CREATE TABLE post_images (
    id          INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    post_id     INT UNSIGNED NOT NULL,
    image_id    INT UNSIGNED NOT NULL,
    created_at  TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT fk_post_images_post
      FOREIGN KEY (post_id) REFERENCES posts(id)
      ON DELETE CASCADE,
    CONSTRAINT fk_post_images_image
      FOREIGN KEY (image_id) REFERENCES images(id)
      ON DELETE CASCADE
);

-- post_images: 게시글당 최대 5개 제한 (API 검증 + DB 방어)
DROP TRIGGER IF EXISTS tr_post_images_max_five;
DELIMITER //
CREATE TRIGGER tr_post_images_max_five
BEFORE INSERT ON post_images
FOR EACH ROW
BEGIN
  IF (SELECT COUNT(*) FROM post_images WHERE post_id = NEW.post_id) >= 5 THEN
    SIGNAL SQLSTATE '45000'
    SET MESSAGE_TEXT = 'post_images: post당 최대 5개';
  END IF;
END//
DELIMITER ;

-- 6. likes (로그인 유저만 좋아요, UNIQUE(post_id, user_id))
CREATE TABLE likes (
    post_id     INT UNSIGNED NOT NULL,
    user_id     INT UNSIGNED NOT NULL,
    created_at  TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (post_id, user_id),

    CONSTRAINT fk_likes_post
      FOREIGN KEY (post_id) REFERENCES posts(id)
      ON DELETE CASCADE,
    CONSTRAINT fk_likes_user
      FOREIGN KEY (user_id) REFERENCES users(id)
      ON DELETE CASCADE
);

-- 7. sessions (로그인 세션)
CREATE TABLE sessions (
    session_id  VARCHAR(255) NOT NULL PRIMARY KEY,
    user_id     INT UNSIGNED NOT NULL,
    created_at  TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    expires_at  TIMESTAMP NOT NULL,

    CONSTRAINT fk_sessions_user
      FOREIGN KEY (user_id) REFERENCES users(id)
      ON DELETE CASCADE
);
-- 확장 시: revoked_at TIMESTAMP NULL 추가 후 로그아웃 시 soft revoke (DELETE 대신 UPDATE).
--         만료(expires_at) 또는 철회(revoked_at)된 세션 주기적 삭제(cleanup)는 앱에서 이미 실행 중.

-- 인덱스 (조회/조인 성능)
CREATE INDEX idx_posts_user_id ON posts(user_id);
CREATE INDEX idx_posts_deleted_at_id ON posts(deleted_at, id DESC);
CREATE INDEX idx_comments_post_id ON comments(post_id);
CREATE INDEX idx_comments_author_id ON comments(author_id);
CREATE INDEX idx_images_uploader_id ON images(uploader_id);
CREATE INDEX idx_images_signup_expires_at ON images(signup_expires_at);
CREATE INDEX idx_post_images_post_id ON post_images(post_id);
CREATE INDEX idx_post_images_image_id ON post_images(image_id);
