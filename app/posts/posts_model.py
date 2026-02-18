# app/posts/posts_model.py
"""게시글 모델 (MySQL posts, post_images 테이블). 게시글-이미지 연결은 post_images."""

import logging
from typing import Optional, List

from app.core.database import get_connection

logger = logging.getLogger(__name__)


class PostsModel:
    """게시글 모델 (MySQL)"""

    MAX_POST_IMAGES = 5

    @classmethod
    def _row_to_post(cls, row: dict, file_rows: Optional[List[dict]] = None) -> dict:
        """DB 행을 API 형식 post dict로 변환. file_rows는 post_images JOIN images 결과(최대 5개)."""
        if not row:
            return None
        post = {
            "postId": row["id"],
            "title": row["title"],
            "content": row["content"],
            "hits": row["view_count"],
            "likeCount": row["like_count"],
            "commentCount": row["comment_count"],
            "authorId": row["user_id"],
            "files": [],
            "createdAt": row["created_at"].strftime("%Y-%m-%d %H:%M:%S")
            if row.get("created_at")
            else "",
        }
        if file_rows:
            for fr in file_rows[: cls.MAX_POST_IMAGES]:
                if fr and fr.get("file_url") is not None:
                    post["files"].append({
                        "fileId": fr["id"],
                        "fileUrl": fr["file_url"],
                        "imageId": fr.get("image_id"),
                    })
        return post

    @classmethod
    def create_post(
        cls, user_id: int, title: str, content: str, image_ids: Optional[List[int]] = None
    ) -> dict:
        """게시글 생성. image_ids는 media 업로드 후 반환된 이미지 ID 목록(최대 5). post_images에 연결."""
        image_ids = image_ids or []
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO posts (user_id, title, content)
                    VALUES (%s, %s, %s)
                    """,
                    (user_id, title, content),
                )
                post_id = cur.lastrowid
                logger.info("게시글 INSERT posts ok post_id=%s user_id=%s", post_id, user_id)
                for iid in image_ids[: cls.MAX_POST_IMAGES]:
                    cur.execute(
                        "INSERT INTO post_images (post_id, image_id) VALUES (%s, %s)",
                        (post_id, iid),
                    )
            conn.commit()
            logger.info("게시글 commit ok post_id=%s", post_id)

        files = [{"fileId": 0, "fileUrl": "", "imageId": iid} for iid in image_ids[: cls.MAX_POST_IMAGES]]
        return {
            "postId": post_id,
            "title": title,
            "content": content,
            "hits": 0,
            "likeCount": 0,
            "commentCount": 0,
            "authorId": user_id,
            "files": files,
            "createdAt": "",
        }

    @classmethod
    def find_post_by_id(cls, post_id: int) -> Optional[dict]:
        """게시글 조회"""
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id, user_id, title, content, view_count, like_count, comment_count, created_at
                    FROM posts WHERE id = %s AND deleted_at IS NULL
                    """,
                    (post_id,),
                )
                row = cur.fetchone()
                if not row:
                    return None

                cur.execute(
                    """
                    SELECT pi.id, i.file_url, i.id AS image_id
                    FROM post_images pi
                    INNER JOIN images i ON pi.image_id = i.id
                    WHERE pi.post_id = %s
                    ORDER BY pi.id
                    """,
                    (post_id,),
                )
                file_rows = cur.fetchall()

        return cls._row_to_post(row, file_rows or None)

    @classmethod
    def get_all_posts(cls, page: int = 1, size: int = 20) -> tuple[List[dict], bool]:
        """무한 스크롤용 목록 조회. (posts, has_more) 반환."""
        offset = (page - 1) * size
        fetch_limit = size + 1
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id, user_id, title, content, view_count, like_count, comment_count, created_at
                    FROM posts WHERE deleted_at IS NULL
                    ORDER BY id DESC LIMIT %s OFFSET %s
                    """,
                    (fetch_limit, offset),
                )
                rows = cur.fetchall()

                has_more = len(rows) > size
                result = []
                for row in rows[:size]:
                    cur.execute(
                        """
                        SELECT pi.id, i.file_url, i.id AS image_id
                        FROM post_images pi
                        INNER JOIN images i ON pi.image_id = i.id
                        WHERE pi.post_id = %s
                        ORDER BY pi.id
                        """,
                        (row["id"],),
                    )
                    file_rows = cur.fetchall()
                    result.append(cls._row_to_post(row, file_rows or None))

        return result, has_more

    @classmethod
    def update_post(
        cls,
        post_id: int,
        title: Optional[str] = None,
        content: Optional[str] = None,
        image_ids: Optional[List[int]] = None,
    ) -> bool:
        """게시글 수정. image_ids 지정 시 기존 첨부를 해당 목록으로 교체(최대 5)."""
        with get_connection() as conn:
            with conn.cursor() as cur:
                if title is not None:
                    cur.execute(
                        "UPDATE posts SET title = %s WHERE id = %s AND deleted_at IS NULL",
                        (title, post_id),
                    )
                if content is not None:
                    cur.execute(
                        "UPDATE posts SET content = %s WHERE id = %s AND deleted_at IS NULL",
                        (content, post_id),
                    )
                if image_ids is not None:
                    cur.execute("DELETE FROM post_images WHERE post_id = %s", (post_id,))
                    for iid in image_ids[: cls.MAX_POST_IMAGES]:
                        cur.execute(
                            "INSERT INTO post_images (post_id, image_id) VALUES (%s, %s)",
                            (post_id, iid),
                        )
            conn.commit()
        return True

    @classmethod
    def delete_post(cls, post_id: int) -> bool:
        """게시글 삭제 (soft delete)"""
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE posts SET deleted_at = NOW() WHERE id = %s",
                    (post_id,),
                )
                affected = cur.rowcount
            conn.commit()
        return affected > 0

    @classmethod
    def increment_hits(cls, post_id: int) -> bool:
        """조회수 증가"""
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE posts SET view_count = view_count + 1 WHERE id = %s AND deleted_at IS NULL",
                    (post_id,),
                )
            conn.commit()
        return True

    @classmethod
    def increment_like_count(cls, post_id: int) -> bool:
        """좋아요 수 증가"""
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE posts SET like_count = like_count + 1 WHERE id = %s",
                    (post_id,),
                )
            conn.commit()
        return True

    @classmethod
    def decrement_like_count(cls, post_id: int) -> bool:
        """좋아요 수 감소"""
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE posts SET like_count = GREATEST(0, like_count - 1) WHERE id = %s",
                    (post_id,),
                )
            conn.commit()
        return True

    @classmethod
    def increment_comment_count(cls, post_id: int) -> bool:
        """댓글 수 증가"""
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE posts SET comment_count = comment_count + 1 WHERE id = %s",
                    (post_id,),
                )
            conn.commit()
        return True

    @classmethod
    def decrement_comment_count(cls, post_id: int) -> bool:
        """댓글 수 감소"""
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE posts SET comment_count = GREATEST(0, comment_count - 1) WHERE id = %s",
                    (post_id,),
                )
            conn.commit()
        return True

    @classmethod
    def count_post_images(cls, post_id: int) -> int:
        """게시글의 이미지 개수"""
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT COUNT(*) as cnt FROM post_images WHERE post_id = %s",
                    (post_id,),
                )
                row = cur.fetchone()
        return row["cnt"] if row else 0

    @classmethod
    def get_post_author_id(cls, post_id: int) -> Optional[int]:
        """게시글 작성자 ID 조회"""
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT user_id FROM posts WHERE id = %s AND deleted_at IS NULL",
                    (post_id,),
                )
                row = cur.fetchone()
        return row["user_id"] if row else None


class PostLikesModel:
    """게시글 좋아요 모델 (MySQL likes 테이블)"""

    @classmethod
    def create_like(cls, post_id: int, user_id: int) -> Optional[dict]:
        """좋아요 생성 (중복 시 None)"""
        try:
            with get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        "INSERT INTO likes (post_id, user_id) VALUES (%s, %s)",
                        (post_id, user_id),
                    )
                conn.commit()
            return {"postId": post_id, "userId": user_id, "createdAt": ""}
        except Exception:
            return None

    @classmethod
    def has_liked(cls, post_id: int, user_id: int) -> bool:
        """좋아요 존재 여부"""
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT 1 FROM likes WHERE post_id = %s AND user_id = %s LIMIT 1",
                    (post_id, user_id),
                )
                return cur.fetchone() is not None

    @classmethod
    def delete_like(cls, post_id: int, user_id: int) -> bool:
        """좋아요 삭제"""
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "DELETE FROM likes WHERE post_id = %s AND user_id = %s",
                    (post_id, user_id),
                )
                affected = cur.rowcount
            conn.commit()
        return affected > 0
