from datetime import datetime, timedelta
from typing import Optional

from fastapi import UploadFile
from sqlalchemy.orm import Session

from app.common import ApiCode, raise_http_error, success_response
from app.core.config import settings
from app.core.dependencies import CurrentUser
from app.media.model import MediaModel
from app.media.image_policy import save_image_for_media


async def upload_image_for_signup(file: Optional[UploadFile], db: Session) -> dict:
    if not file:
        raise_http_error(400, ApiCode.MISSING_REQUIRED_FIELD)
    file_key, file_url, content_type, size = await save_image_for_media(
        file, purpose="profile"
    )
    expires_at = datetime.now() + timedelta(seconds=settings.SIGNUP_IMAGE_TOKEN_TTL_SECONDS)
    row = MediaModel.create_signup_image(
        file_key=file_key,
        file_url=file_url,
        content_type=content_type,
        size=size,
        expires_at=expires_at,
        db=db,
    )
    return success_response(
        ApiCode.IMAGE_UPLOADED,
        {"imageId": row["id"], "url": row["file_url"], "signupToken": row["signup_token"]},
    )


async def upload_image(file: Optional[UploadFile], user: CurrentUser, purpose: str, db: Session) -> dict:
    if not file:
        raise_http_error(400, ApiCode.MISSING_REQUIRED_FIELD)
    file_key, file_url, content_type, size = await save_image_for_media(file, purpose=purpose)
    row = MediaModel.create_image(
        file_key=file_key,
        file_url=file_url,
        content_type=content_type,
        size=size,
        uploader_id=user.id,
        db=db,
    )
    return success_response(ApiCode.IMAGE_UPLOADED, {"imageId": row["id"], "url": row["file_url"]})


def withdraw_image(image_id: int, user: CurrentUser, db: Session) -> None:
    if not MediaModel.withdraw_image_by_owner(image_id, user.id, db=db):
        raise_http_error(404, ApiCode.IMAGE_NOT_FOUND)
