# app/media/model.py

from typing import Optional, Any

from app.core.database import get_connection


class MediaModel:
    @classmethod
    def create_image(cls, file_key: str, file_url: str, content_type: Optional[str] = None, size: Optional[int] = None, uploader_id: Optional[int] = None) -> dict:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO images (file_key, file_url, content_type, size, uploader_id)
                    VALUES (%s, %s, %s, %s, %s)
                    """,
                    (file_key, file_url, content_type, size, uploader_id),
                )
                image_id = cur.lastrowid
            conn.commit()
        return {"id": image_id, "file_url": file_url}

    @classmethod
    def get_url_by_id(cls, image_id: int) -> Optional[str]:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT file_url FROM images WHERE id = %s AND deleted_at IS NULL",
                    (image_id,),
                )
                row = cur.fetchone()
        return row["file_url"] if row else None

    @classmethod
    def withdraw_image_by_owner(cls, image_id: int, user_id: int) -> bool:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE images SET deleted_at = NOW() WHERE id = %s AND uploader_id = %s AND deleted_at IS NULL",
                    (image_id, user_id),
                )
                affected = cur.rowcount
            conn.commit()
        return affected > 0

    @classmethod
    def withdraw_by_url(cls, file_url: str, conn: Optional[Any] = None) -> bool:
        if not file_url or not file_url.strip():
            return False
        url = file_url.strip()

        def _do(c):
            with c.cursor() as cur:
                cur.execute(
                    "UPDATE images SET deleted_at = NOW() WHERE file_url = %s AND deleted_at IS NULL",
                    (url,),
                )
                return cur.rowcount > 0

        if conn is not None:
            return _do(conn)
        with get_connection() as conn:
            if not _do(conn):
                return False
            conn.commit()
        return True
