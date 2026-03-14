-- puppytalk DB 데이터만 전부 비우기 (테이블 구조 유지, 시퀀스 리셋)
-- 사용: psql -U postgres -d puppytalk -f docs/clear_db.sql

TRUNCATE TABLE likes, post_images, comments, posts, dog_profiles, images, users RESTART IDENTITY CASCADE;
