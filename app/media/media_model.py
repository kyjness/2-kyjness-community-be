# app/media/media_model.py
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
                    "SELECT file_url FROM images WHERE id = %s",
                    (image_id,),
                )
                row = cur.fetchone()
        return row["file_url"] if row else None

    @classmethod
    def get_id_by_url(cls, file_url: str) -> Optional[int]:
        """file_url로 images 테이블의 id 조회. 게시글 수정 시 기존 이미지 유지용."""
        if not file_url:
            return None
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT id FROM images WHERE file_url = %s LIMIT 1",
                    (file_url,),
                )
                row = cur.fetchone()
        return row["id"] if row else None
