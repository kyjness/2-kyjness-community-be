# app/media/media_controller.py
"""이미지 업로드 통합. POST /v1/media/images → imageId, url 반환."""

from typing import Optional

from fastapi import UploadFile

from app.core.file_upload import save_image_for_media
from app.core.codes import ApiCode
from app.core.response import success_response, raise_http_error
from app.media.media_model import MediaModel


async def upload_image(
    file: Optional[UploadFile],
    user_id: Optional[int] = None,
    folder: str = "post",
) -> dict:
    """이미지 1건 업로드. folder: profile | post. 저장 후 images 테이블에 메타 저장, imageId·url 반환."""
    if not file:
        raise_http_error(400, ApiCode.MISSING_REQUIRED_FIELD)
    file_key, file_url, content_type, size = await save_image_for_media(file, folder=folder)
    row = MediaModel.create_image(
        file_key=file_key,
        file_url=file_url,
        content_type=content_type,
        size=size,
        uploader_id=user_id,
    )
    return success_response(ApiCode.OK, {"imageId": row["imageId"], "url": row["fileUrl"]})
