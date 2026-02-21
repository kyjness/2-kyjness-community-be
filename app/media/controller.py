# app/media/controller.py
"""이미지 업로드 통합."""

from typing import Optional

from fastapi import UploadFile

from app.core.file_upload import save_image_for_media
from app.core.codes import ApiCode
from app.core.response import success_response, raise_http_error
from app.media.model import MediaModel


def withdraw_image(image_id: int, user_id: int) -> None:
    img = MediaModel.get_image_for_withdraw(image_id)
    if not img:
        raise_http_error(404, ApiCode.IMAGE_NOT_FOUND)
    uploader_id = img.get("uploader_id")
    if uploader_id is not None and int(uploader_id) != user_id:
        raise_http_error(403, ApiCode.FORBIDDEN)
    if not MediaModel.withdraw_image(image_id):
        raise_http_error(404, ApiCode.IMAGE_NOT_FOUND)


async def upload_image(
    file: Optional[UploadFile],
    user_id: Optional[int] = None,
    folder: str = "post",
) -> dict:
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
