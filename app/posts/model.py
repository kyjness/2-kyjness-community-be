# app/posts/model.py
"""게시글 모델 (posts, post_images, likes 테이블)."""

import logging
from datetime import datetime
from typing import Optional, List

import pymysql

from app.core.database import get_connection

logger = logging.getLogger(__name__)


class PostsModel:
    MAX_POST_IMAGES = 5

    @classmethod
    def _row_to_post(cls, row: dict, file_rows: Optional[List[dict]] = None) -> dict:
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
        image_ids = image_ids or []
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO posts (user_id, title, content) VALUES (%s, %s, %s)",
                    (user_id, title, content),
                )
                post_id = cur.lastrowid
                for iid in image_ids[: cls.MAX_POST_IMAGES]:
                    cur.execute(
                        "INSERT INTO post_images (post_id, image_id) VALUES (%s, %s)",
                        (post_id, iid),
                    )
                file_rows = []
                if image_ids:
                    cur.execute(
                        """
                        SELECT pi.id, i.file_url, i.id AS image_id
                        FROM post_images pi
                        INNER JOIN images i ON pi.image_id = i.id AND i.deleted_at IS NULL
                        WHERE pi.post_id = %s ORDER BY pi.id
                        """,
                        (post_id,),
                    )
                    file_rows = cur.fetchall()
                cur.execute("SELECT created_at FROM posts WHERE id = %s", (post_id,))
                created_row = cur.fetchone()
                created_at = (
                    created_row["created_at"].strftime("%Y-%m-%d %H:%M:%S")
                    if created_row and created_row.get("created_at")
                    else datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                )
            conn.commit()
        files = [
            {"fileId": fr["id"], "fileUrl": fr["file_url"] or "", "imageId": fr["image_id"]}
            for fr in file_rows
        ]
        return {
            "postId": post_id,
            "title": title,
            "content": content,
            "hits": 0,
            "likeCount": 0,
            "commentCount": 0,
            "authorId": user_id,
            "files": files,
            "createdAt": created_at,
        }

    @classmethod
    def find_post_by_id(cls, post_id: int) -> Optional[dict]:
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
                    INNER JOIN images i ON pi.image_id = i.id AND i.deleted_at IS NULL
                    WHERE pi.post_id = %s ORDER BY pi.id
                    """,
                    (post_id,),
                )
                file_rows = cur.fetchall()
        return cls._row_to_post(row, file_rows or None)

    @classmethod
    def get_all_posts(cls, page: int = 1, size: int = 20) -> tuple[List[dict], bool]:
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
                rows = rows[:size]
                if not rows:
                    return [], has_more
                post_ids = [r["id"] for r in rows]
                placeholders = ", ".join(["%s"] * len(post_ids))
                cur.execute(
                    f"""
                    SELECT pi.post_id, pi.id, i.file_url, i.id AS image_id
                    FROM post_images pi
                    INNER JOIN images i ON pi.image_id = i.id AND i.deleted_at IS NULL
                    WHERE pi.post_id IN ({placeholders})
                    ORDER BY pi.post_id, pi.id
                    """,
                    tuple(post_ids),
                )
                all_file_rows = cur.fetchall()
                files_by_post: dict[int, list] = {pid: [] for pid in post_ids}
                for fr in all_file_rows:
                    files_by_post[fr["post_id"]].append(fr)
                result = [
                    cls._row_to_post(row, files_by_post.get(row["id"]) or None)
                    for row in rows
                ]
        return result, has_more

    @classmethod
    def update_post(
        cls,
        post_id: int,
        title: Optional[str] = None,
        content: Optional[str] = None,
        image_ids: Optional[List[int]] = None,
    ) -> bool:
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
                    cur.execute("SELECT image_id FROM post_images WHERE post_id = %s", (post_id,))
                    old_image_ids = {r["image_id"] for r in cur.fetchall()}
                    new_image_ids_set = set(image_ids[: cls.MAX_POST_IMAGES])
                    removed_ids = old_image_ids - new_image_ids_set
                    cur.execute("DELETE FROM post_images WHERE post_id = %s", (post_id,))
                    for iid in image_ids[: cls.MAX_POST_IMAGES]:
                        cur.execute(
                            "INSERT INTO post_images (post_id, image_id) VALUES (%s, %s)",
                            (post_id, iid),
                        )
                    for img_id in removed_ids:
                        cur.execute("SELECT 1 FROM post_images WHERE image_id = %s LIMIT 1", (img_id,))
                        if cur.fetchone() is None:
                            cur.execute(
                                "UPDATE images SET deleted_at = NOW() WHERE id = %s AND deleted_at IS NULL",
                                (img_id,),
                            )
            conn.commit()
        return True

    @classmethod
    def withdraw_post(cls, post_id: int) -> bool:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE comments SET deleted_at = NOW() WHERE post_id = %s AND deleted_at IS NULL",
                    (post_id,),
                )
                cur.execute("DELETE FROM likes WHERE post_id = %s", (post_id,))
                cur.execute("SELECT image_id FROM post_images WHERE post_id = %s", (post_id,))
                image_ids = [r["image_id"] for r in cur.fetchall()]
                cur.execute("DELETE FROM post_images WHERE post_id = %s", (post_id,))
                for img_id in image_ids:
                    cur.execute("SELECT 1 FROM post_images WHERE image_id = %s LIMIT 1", (img_id,))
                    if cur.fetchone() is None:
                        cur.execute(
                            "UPDATE images SET deleted_at = NOW() WHERE id = %s AND deleted_at IS NULL",
                            (img_id,),
                        )
                cur.execute("UPDATE posts SET deleted_at = NOW() WHERE id = %s", (post_id,))
                affected = cur.rowcount
            conn.commit()
        return affected > 0

    @classmethod
    def increment_hits(cls, post_id: int) -> bool:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE posts SET view_count = view_count + 1 WHERE id = %s AND deleted_at IS NULL",
                    (post_id,),
                )
            conn.commit()
        return True

    @classmethod
    def increment_like_count(cls, post_id: int) -> int:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("UPDATE posts SET like_count = like_count + 1 WHERE id = %s", (post_id,))
                cur.execute("SELECT like_count FROM posts WHERE id = %s", (post_id,))
                row = cur.fetchone()
            conn.commit()
        return row["like_count"] if row else 0

    @classmethod
    def decrement_like_count(cls, post_id: int) -> int:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE posts SET like_count = GREATEST(0, like_count - 1) WHERE id = %s",
                    (post_id,),
                )
                cur.execute("SELECT like_count FROM posts WHERE id = %s", (post_id,))
                row = cur.fetchone()
            conn.commit()
        return row["like_count"] if row else 0

    @classmethod
    def increment_comment_count(cls, post_id: int) -> bool:
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
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE posts SET comment_count = GREATEST(0, comment_count - 1) WHERE id = %s",
                    (post_id,),
                )
            conn.commit()
        return True


class PostLikesModel:
    @classmethod
    def _liker_key_user(cls, user_id: int) -> str:
        return f"u_{user_id}"

    @classmethod
    def has_liked(cls, post_id: int, liker_key: str) -> bool:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT 1 FROM likes WHERE post_id = %s AND liker_key = %s LIMIT 1",
                    (post_id, liker_key),
                )
                return cur.fetchone() is not None

    @classmethod
    def create_like(cls, post_id: int, liker_key: str, user_id: Optional[int] = None) -> Optional[dict]:
        try:
            with get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        "INSERT INTO likes (post_id, liker_key, user_id) VALUES (%s, %s, %s)",
                        (post_id, liker_key, user_id),
                    )
                conn.commit()
            return {"postId": post_id, "likerKey": liker_key}
        except pymysql.err.IntegrityError:
            return None
        except Exception as e:
            logger.exception("likes INSERT 실패: %s", e)
            raise

    @classmethod
    def delete_like(cls, post_id: int, liker_key: str) -> bool:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "DELETE FROM likes WHERE post_id = %s AND liker_key = %s",
                    (post_id, liker_key),
                )
                affected = cur.rowcount
            conn.commit()
        return affected > 0
