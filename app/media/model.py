# app/media/model.py
"""이미지 업로드 메타 저장 (images 테이블)."""

from typing import Optional

from app.core.database import get_connection


class MediaModel:
    @classmethod
    def create_image(
        cls,
        file_key: str,
        file_url: str,
        content_type: Optional[str] = None,
        size: Optional[int] = None,
        uploader_id: Optional[int] = None,
    ) -> dict:
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
        return {"imageId": image_id, "fileUrl": file_url}

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
    def withdraw_image(cls, image_id: int) -> bool:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE images SET deleted_at = NOW() WHERE id = %s AND deleted_at IS NULL",
                    (image_id,),
                )
                affected = cur.rowcount
            conn.commit()
        return affected > 0

    @classmethod
    def get_image_for_withdraw(cls, image_id: int) -> Optional[dict]:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT id, uploader_id FROM images WHERE id = %s AND deleted_at IS NULL LIMIT 1",
                    (image_id,),
                )
                return cur.fetchone()

    @classmethod
    def withdraw_by_url(cls, file_url: str) -> bool:
        if not file_url or not file_url.strip():
            return False
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT id FROM images WHERE file_url = %s AND deleted_at IS NULL LIMIT 1",
                    (file_url.strip(),),
                )
                row = cur.fetchone()
                if not row:
                    return False
                cur.execute("UPDATE images SET deleted_at = NOW() WHERE id = %s", (row["id"],))
            conn.commit()
        return True
