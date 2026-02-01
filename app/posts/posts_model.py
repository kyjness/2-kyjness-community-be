# app/posts/posts_model.py
"""게시글 모델 (MySQL posts, post_files 테이블)"""

from typing import Optional, List

from app.core.database import get_connection


class PostsModel:
    """게시글 모델 (MySQL)"""

    @classmethod
    def _row_to_post(cls, row: dict, file_row: Optional[dict] = None) -> dict:
        """DB 행을 API 형식 post dict로 변환"""
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
            "file": None,
            "createdAt": row["created_at"].strftime("%Y-%m-%d %H:%M:%S")
            if row.get("created_at")
            else "",
        }
        if file_row and file_row.get("file_url"):
            post["file"] = {
                "fileId": file_row["id"],
                "fileUrl": file_row["file_url"],
            }
        return post

    @classmethod
    def create_post(
        cls, user_id: int, title: str, content: str, file_url: str = ""
    ) -> dict:
        """게시글 생성"""
        conn = get_connection()
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO posts (user_id, title, content)
                VALUES (%s, %s, %s)
                """,
                (user_id, title, content),
            )
            post_id = cur.lastrowid

            file_id = None
            if file_url:
                cur.execute(
                    """
                    INSERT INTO post_files (post_id, file_url)
                    VALUES (%s, %s)
                    """,
                    (post_id, file_url),
                )
                file_id = cur.lastrowid

        conn.commit()

        file_info = (
            {"fileId": file_id, "fileUrl": file_url} if file_url and file_id else None
        )
        return {
            "postId": post_id,
            "title": title,
            "content": content,
            "hits": 0,
            "likeCount": 0,
            "commentCount": 0,
            "authorId": user_id,
            "file": file_info,
            "createdAt": "",
        }

    @classmethod
    def find_post_by_id(cls, post_id: int) -> Optional[dict]:
        """게시글 조회"""
        conn = get_connection()
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
                "SELECT id, file_url FROM post_files WHERE post_id = %s AND deleted_at IS NULL LIMIT 1",
                (post_id,),
            )
            file_row = cur.fetchone()

        return cls._row_to_post(row, file_row)

    @classmethod
    def get_all_posts(cls, page: int = 1, size: int = 20) -> List[dict]:
        """페이징 목록 조회"""
        conn = get_connection()
        offset = (page - 1) * size
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, user_id, title, content, view_count, like_count, comment_count, created_at
                FROM posts WHERE deleted_at IS NULL
                ORDER BY id DESC LIMIT %s OFFSET %s
                """,
                (size, offset),
            )
            rows = cur.fetchall()

            result = []
            for row in rows:
                cur.execute(
                    "SELECT id, file_url FROM post_files WHERE post_id = %s AND deleted_at IS NULL LIMIT 1",
                    (row["id"],),
                )
                file_row = cur.fetchone()
                result.append(cls._row_to_post(row, file_row))

        return result

    @classmethod
    def update_post(
        cls,
        post_id: int,
        title: Optional[str] = None,
        content: Optional[str] = None,
        file_url: Optional[str] = None,
    ) -> bool:
        """게시글 수정"""
        conn = get_connection()
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

            if file_url is not None:
                cur.execute(
                    "SELECT id FROM post_files WHERE post_id = %s AND deleted_at IS NULL LIMIT 1",
                    (post_id,),
                )
                existing = cur.fetchone()
                if file_url:
                    if existing:
                        cur.execute(
                            "UPDATE post_files SET file_url = %s WHERE id = %s",
                            (file_url, existing["id"]),
                        )
                    else:
                        cur.execute(
                            "INSERT INTO post_files (post_id, file_url) VALUES (%s, %s)",
                            (post_id, file_url),
                        )
                else:
                    if existing:
                        cur.execute(
                            "UPDATE post_files SET deleted_at = NOW() WHERE id = %s",
                            (existing["id"],),
                        )

        conn.commit()
        return True

    @classmethod
    def delete_post(cls, post_id: int) -> bool:
        """게시글 삭제 (soft delete)"""
        conn = get_connection()
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
        conn = get_connection()
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
        conn = get_connection()
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
        conn = get_connection()
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
        conn = get_connection()
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
        conn = get_connection()
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE posts SET comment_count = GREATEST(0, comment_count - 1) WHERE id = %s",
                (post_id,),
            )
        conn.commit()
        return True

    @classmethod
    def get_post_author_id(cls, post_id: int) -> Optional[int]:
        """게시글 작성자 ID 조회"""
        conn = get_connection()
        with conn.cursor() as cur:
            cur.execute(
                "SELECT user_id FROM posts WHERE id = %s AND deleted_at IS NULL",
                (post_id,),
            )
            row = cur.fetchone()
        return row["user_id"] if row else None
