# app/media/controller.py

from typing import Optional

from fastapi import UploadFile

from app.core.file_upload import save_image_for_media
from app.core.codes import ApiCode
from app.core.response import success_response, raise_http_error
from app.media.model import MediaModel


async def upload_image(file: Optional[UploadFile], user_id: int, folder: str = "post") -> dict:
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
    return success_response(ApiCode.OK, {"imageId": row["id"], "url": row["file_url"]})

def withdraw_image(image_id: int, user_id: int) -> None:
    if not MediaModel.withdraw_image_by_owner(image_id, user_id):
        raise_http_error(404, ApiCode.IMAGE_NOT_FOUND)
