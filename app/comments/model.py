# app/comments/model.py
"""댓글 모델 (comments 테이블)."""

from typing import Optional, List

from app.core.database import get_connection


class CommentsModel:
    @classmethod
    def _row_to_comment(cls, row: dict) -> dict:
        if not row:
            return None
        return {
            "commentId": row["id"],
            "postId": row["post_id"],
            "content": row["content"],
            "authorId": row["author_id"],
            "createdAt": row["created_at"].strftime("%Y-%m-%d %H:%M:%S")
            if row.get("created_at")
            else "",
        }

    @classmethod
    def create_comment(cls, post_id: int, user_id: int, content: str) -> dict:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO comments (post_id, author_id, content) VALUES (%s, %s, %s)",
                    (post_id, user_id, content),
                )
                comment_id = cur.lastrowid
            conn.commit()
        return {
            "commentId": comment_id,
            "postId": post_id,
            "content": content,
            "authorId": user_id,
            "createdAt": "",
        }

    @classmethod
    def find_comment_by_id(cls, comment_id: int) -> Optional[dict]:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id, post_id, author_id, content, created_at
                    FROM comments WHERE id = %s AND deleted_at IS NULL
                    """,
                    (comment_id,),
                )
                row = cur.fetchone()
        return cls._row_to_comment(row) if row else None

    @classmethod
    def get_comments_by_post_id(cls, post_id: int, page: int = 1, size: int = 10) -> List[dict]:
        offset = (page - 1) * size
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id, post_id, author_id, content, created_at
                    FROM comments WHERE post_id = %s AND deleted_at IS NULL
                    ORDER BY id DESC LIMIT %s OFFSET %s
                    """,
                    (post_id, size, offset),
                )
                rows = cur.fetchall()
        return [cls._row_to_comment(r) for r in rows]

    @classmethod
    def get_comment_count_by_post_id(cls, post_id: int) -> int:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT COUNT(*) AS cnt FROM comments WHERE post_id = %s AND deleted_at IS NULL",
                    (post_id,),
                )
                row = cur.fetchone()
        return row["cnt"] or 0

    @classmethod
    def update_comment(cls, comment_id: int, content: str) -> bool:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE comments SET content = %s WHERE id = %s AND deleted_at IS NULL",
                    (content, comment_id),
                )
                affected = cur.rowcount
            conn.commit()
        return affected > 0

    @classmethod
    def withdraw_comment(cls, comment_id: int) -> bool:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("UPDATE comments SET deleted_at = NOW() WHERE id = %s", (comment_id,))
                affected = cur.rowcount
            conn.commit()
        return affected > 0
