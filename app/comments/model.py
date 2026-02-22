# app/comments/model.py

from typing import Any, Optional, List

from app.core.database import get_connection


class CommentsModel:
    @classmethod
    def create_comment(cls, post_id: int, user_id: int, content: str, conn: Optional[Any] = None) -> dict:
        """conn 주입 시 commit 안 함(호출자가 commit). 카운트 정합성 위해 같은 conn으로
        create_comment + increment_comment_count 후 한 번만 commit 하는 사용을 권장."""
        def _do_insert(c):
            with c.cursor() as cur:
                cur.execute(
                    "INSERT INTO comments (post_id, author_id, content) VALUES (%s, %s, %s)",
                    (post_id, user_id, content),
                )
                comment_id = cur.lastrowid
                cur.execute(
                    "SELECT id, post_id, author_id, content, created_at FROM comments WHERE id = %s",
                    (comment_id,),
                )
                return cur.fetchone()
        if conn is not None:
            return _do_insert(conn)
        with get_connection() as conn:
            row = _do_insert(conn)
            conn.commit()
        return row

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
                return cur.fetchone()

    @classmethod
    def get_comments_by_post_id(cls, post_id: int, page: int = 1, size: int = 10) -> List[dict]:
        """댓글 목록 + 작성자 정보. users JOIN으로 N+1 방지."""
        offset = (page - 1) * size
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT c.id, c.post_id, c.author_id, c.content, c.created_at,
                           u.id AS author_user_id, u.nickname AS author_nickname,
                           u.profile_image_url AS author_profile_image_url
                    FROM comments c
                    INNER JOIN users u ON u.id = c.author_id AND u.deleted_at IS NULL
                    WHERE c.post_id = %s AND c.deleted_at IS NULL
                    ORDER BY c.id DESC LIMIT %s OFFSET %s
                    """,
                    (post_id, size, offset),
                )
                return cur.fetchall()

    @classmethod
    def get_comment_count_by_post_id(cls, post_id: int) -> int:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT COUNT(*) AS cnt FROM comments WHERE post_id = %s AND deleted_at IS NULL",
                    (post_id,),
                )
                row = cur.fetchone()
        return int(row["cnt"])

    @classmethod
    def update_comment(cls, post_id: int, comment_id: int, content: str) -> int:
        """수정된 행 수. 0이면 해당 글의 댓글이 아니거나 없음/이미 삭제됨. post_id로 다른 글 댓글 수정 차단."""
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE comments SET content = %s WHERE id = %s AND post_id = %s AND deleted_at IS NULL",
                    (content, comment_id, post_id),
                )
                affected = cur.rowcount
            conn.commit()
        return affected

    @classmethod
    def withdraw_comment(cls, post_id: int, comment_id: int, conn: Optional[Any] = None) -> bool:
        """삭제된 행 수 > 0. post_id로 다른 글 댓글 삭제 차단."""
        if conn is not None:
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE comments SET deleted_at = NOW() WHERE id = %s AND post_id = %s",
                    (comment_id, post_id),
                )
                affected = cur.rowcount
            return affected > 0
        with get_connection() as c:
            with c.cursor() as cur:
                cur.execute(
                    "UPDATE comments SET deleted_at = NOW() WHERE id = %s AND post_id = %s",
                    (comment_id, post_id),
                )
                affected = cur.rowcount
            c.commit()
        return affected > 0
