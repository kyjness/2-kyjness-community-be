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
CREATE TABLE images (
    id              INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    file_key        VARCHAR(255) NOT NULL COMMENT '저장 경로(profile/xxx.jpg 또는 post/xxx.jpg)',
    file_url        VARCHAR(999) NOT NULL COMMENT '공개 URL',
    content_type    VARCHAR(255) NULL,
    size            INT UNSIGNED NULL,
    uploader_id     INT UNSIGNED NULL COMMENT '업로더(비회원 가입 전이면 NULL)',
    created_at      TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT fk_images_uploader FOREIGN KEY (uploader_id) REFERENCES users(id) ON DELETE SET NULL
);

-- 5. post_images (게시글-이미지 연결 테이블. 어떤 게시글에 어떤 이미지가 붙는지)
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

-- 6. likes (중복 좋아요 방지: 복합 PK, 하드 삭제)
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


-- 인덱스(권장: 조회/조인 성능)
CREATE INDEX idx_posts_user_id ON posts(user_id);
CREATE INDEX idx_comments_post_id ON comments(post_id);
CREATE INDEX idx_comments_author_id ON comments(author_id);
CREATE INDEX idx_images_uploader_id ON images(uploader_id);
CREATE INDEX idx_post_images_post_id ON post_images(post_id);
CREATE INDEX idx_post_images_image_id ON post_images(image_id);