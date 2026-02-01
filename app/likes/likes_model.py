# app/likes/likes_model.py
"""좋아요 모델 (MySQL likes 테이블)"""

from typing import Optional, List

from app.core.database import get_connection


class LikesModel:
    """좋아요 모델 (MySQL)"""

    @classmethod
    def create_like(cls, post_id: int, user_id: int) -> Optional[dict]:
        """좋아요 생성 (중복 시 None)"""
        conn = get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO likes (post_id, user_id)
                    VALUES (%s, %s)
                    """,
                    (post_id, user_id),
                )
            conn.commit()
            return {"postId": post_id, "userId": user_id, "createdAt": ""}
        except Exception:
            conn.rollback()
            return None  # 중복 등

    @classmethod
    def find_like(cls, post_id: int, user_id: int) -> Optional[dict]:
        """좋아요 조회"""
        conn = get_connection()
        with conn.cursor() as cur:
            cur.execute(
                "SELECT post_id, user_id FROM likes WHERE post_id = %s AND user_id = %s",
                (post_id, user_id),
            )
            row = cur.fetchone()
        return (
            {"postId": row["post_id"], "userId": row["user_id"], "createdAt": ""}
            if row
            else None
        )

    @classmethod
    def has_liked(cls, post_id: int, user_id: int) -> bool:
        """좋아요 존재 여부"""
        conn = get_connection()
        with conn.cursor() as cur:
            cur.execute(
                "SELECT 1 FROM likes WHERE post_id = %s AND user_id = %s LIMIT 1",
                (post_id, user_id),
            )
            return cur.fetchone() is not None

    @classmethod
    def delete_like(cls, post_id: int, user_id: int) -> bool:
        """좋아요 삭제"""
        conn = get_connection()
        with conn.cursor() as cur:
            cur.execute(
                "DELETE FROM likes WHERE post_id = %s AND user_id = %s",
                (post_id, user_id),
            )
            affected = cur.rowcount
        conn.commit()
        return affected > 0

    @classmethod
    def get_like_count_by_post_id(cls, post_id: int) -> int:
        """게시글별 좋아요 수"""
        conn = get_connection()
        with conn.cursor() as cur:
            cur.execute(
                "SELECT COUNT(*) AS cnt FROM likes WHERE post_id = %s",
                (post_id,),
            )
            row = cur.fetchone()
        return row["cnt"] or 0

    @classmethod
    def get_liked_posts_by_user_id(cls, user_id: int) -> List[int]:
        """사용자가 좋아요한 게시글 ID 목록"""
        conn = get_connection()
        with conn.cursor() as cur:
            cur.execute(
                "SELECT post_id FROM likes WHERE user_id = %s",
                (user_id,),
            )
            rows = cur.fetchall()
        return [r["post_id"] for r in rows]
