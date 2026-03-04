# 이미지 업로드 비즈니스 로직. Model은 Image ORM 반환, Controller에서 Schema로 직렬화.
from datetime import timedelta

from fastapi import UploadFile
from sqlalchemy.orm import Session

from app.common import ApiCode, raise_http_error, success_response
from app.core.config import settings
from app.db import utc_now
from app.api.dependencies import CurrentUser
from app.core.storage import storage_delete
from app.media.model import MediaModel
from app.media.schema import ImageUploadResponse
from app.media.image_policy import save_image_for_media


async def upload_image_for_signup(file: UploadFile, db: Session) -> dict:
    file_key, file_url, content_type, size = await save_image_for_media(
        file, purpose="signup"
    )
    try:
        expires_at = utc_now() + timedelta(seconds=settings.SIGNUP_IMAGE_TOKEN_TTL_SECONDS)
        image, signup_token = MediaModel.create_signup_image(
            file_key=file_key,
            file_url=file_url,
            content_type=content_type,
            size=size,
            expires_at=expires_at,
            db=db,
        )
    except Exception:
        try:
            storage_delete(file_key)
        except Exception:
            pass
        raise
    payload = ImageUploadResponse.model_validate(image).model_dump(by_alias=True)
    payload["signupToken"] = signup_token
    return success_response(ApiCode.IMAGE_UPLOADED, payload)


async def upload_image(
    file: UploadFile,
    user: CurrentUser,
    purpose: str,
    db: Session,
) -> dict:
    if purpose not in ("profile", "post"):
        raise_http_error(400, ApiCode.INVALID_REQUEST)
    file_key, file_url, content_type, size = await save_image_for_media(file, purpose=purpose)
    try:
        image = MediaModel.create_image(
            file_key=file_key,
            file_url=file_url,
            content_type=content_type,
            size=size,
            uploader_id=user.id,
            db=db,
        )
    except Exception:
        try:
            storage_delete(file_key)
        except Exception:
            pass
        raise
    payload = ImageUploadResponse.model_validate(image).model_dump(by_alias=True)
    return success_response(ApiCode.IMAGE_UPLOADED, payload)


def delete_image(image_id: int, user: CurrentUser, db: Session) -> None:
    try:
        if not MediaModel.delete_image_by_owner(image_id, user.id, db=db):
            raise_http_error(404, ApiCode.IMAGE_NOT_FOUND)
    except ValueError as e:
        if "IMAGE_IN_USE" in str(e):
            raise_http_error(409, ApiCode.CONFLICT)
        raise
