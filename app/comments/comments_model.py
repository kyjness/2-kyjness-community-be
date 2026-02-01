# app/comments/comments_model.py
"""댓글 모델 (MySQL comments 테이블)"""

from typing import Optional, List

from app.core.database import get_connection


class CommentsModel:
    """댓글 모델 (MySQL)"""

    @classmethod
    def _row_to_comment(cls, row: dict) -> dict:
        """DB 행을 API 형식 comment dict로 변환"""
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
        """댓글 생성"""
        conn = get_connection()
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO comments (post_id, author_id, content)
                VALUES (%s, %s, %s)
                """,
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
        """댓글 조회"""
        conn = get_connection()
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
    def get_comments_by_post_id(
        cls, post_id: int, page: int = 1, size: int = 20
    ) -> List[dict]:
        """특정 게시글의 댓글 목록 (페이징)"""
        conn = get_connection()
        offset = (page - 1) * size
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, post_id, author_id, content, created_at
                FROM comments
                WHERE post_id = %s AND deleted_at IS NULL
                ORDER BY id DESC
                LIMIT %s OFFSET %s
                """,
                (post_id, size, offset),
            )
            rows = cur.fetchall()
        return [cls._row_to_comment(r) for r in rows]

    @classmethod
    def update_comment(cls, comment_id: int, content: str) -> bool:
        """댓글 수정"""
        conn = get_connection()
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE comments SET content = %s WHERE id = %s AND deleted_at IS NULL",
                (content, comment_id),
            )
            affected = cur.rowcount
        conn.commit()
        return affected > 0

    @classmethod
    def delete_comment(cls, comment_id: int) -> bool:
        """댓글 삭제 (soft delete)"""
        conn = get_connection()
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE comments SET deleted_at = NOW() WHERE id = %s",
                (comment_id,),
            )
            affected = cur.rowcount
        conn.commit()
        return affected > 0

    @classmethod
    def get_comment_author_id(cls, comment_id: int) -> Optional[int]:
        """댓글 작성자 ID 조회"""
        conn = get_connection()
        with conn.cursor() as cur:
            cur.execute(
                "SELECT author_id FROM comments WHERE id = %s AND deleted_at IS NULL",
                (comment_id,),
            )
            row = cur.fetchone()
        return row["author_id"] if row else None

    @classmethod
    def get_comment_post_id(cls, comment_id: int) -> Optional[int]:
        """댓글의 게시글 ID 조회"""
        conn = get_connection()
        with conn.cursor() as cur:
            cur.execute(
                "SELECT post_id FROM comments WHERE id = %s AND deleted_at IS NULL",
                (comment_id,),
            )
            row = cur.fetchone()
        return row["post_id"] if row else None
