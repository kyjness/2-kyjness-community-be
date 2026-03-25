# 미디어 라우터. Router → Service. 예외는 전역 handler 처리.
from typing import Literal

from fastapi import APIRouter, Depends, File, Header, Path, Query, Request, UploadFile
from fastapi.responses import Response
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import (
    MEDIA_SIGNUP_IDEMPOTENT_RESPONSE_ATTR,
    MEDIA_UPLOAD_IDEMPOTENT_RESPONSE_ATTR,
    CurrentUser,
    check_upload_content_length,
    get_current_user,
    get_master_db,
    media_image_upload_idempotency_prepare,
    media_signup_upload_idempotency_after_failure,
    media_signup_upload_idempotency_after_success,
    media_signup_upload_idempotency_prepare,
    media_upload_idempotency_after_failure,
    media_upload_idempotency_after_success,
)
from app.common import ApiCode, ApiResponse, api_response
from app.media.schema import ImageUploadResponse, SignupImageUploadData
from app.media.service import MediaService

router = APIRouter(prefix="/media", tags=["media"])


@router.post(
    "/images/signup",
    status_code=201,
    response_model=ApiResponse[SignupImageUploadData],
    dependencies=[
        Depends(check_upload_content_length),
        Depends(media_signup_upload_idempotency_prepare),
    ],
)
async def upload_image_signup(
    request: Request,
    x_idempotency_key: str | None = Header(default=None, alias="X-Idempotency-Key"),
    image: UploadFile = File(..., description="회원가입용 프로필 이미지"),
    db: AsyncSession = Depends(get_master_db),
):
    redis: Redis | None = getattr(request.app.state, "redis", None)
    hit = getattr(request.state, MEDIA_SIGNUP_IDEMPOTENT_RESPONSE_ATTR, None)
    if hit is not None:
        delattr(request.state, MEDIA_SIGNUP_IDEMPOTENT_RESPONSE_ATTR)
        return hit
    try:
        data = await MediaService.upload_image_for_signup(image, db=db, redis=redis)
        out = api_response(request, code=ApiCode.IMAGE_UPLOADED, data=data)
        await media_signup_upload_idempotency_after_success(request, x_idempotency_key, out)
        return out
    except Exception:
        await media_signup_upload_idempotency_after_failure(request, x_idempotency_key)
        raise


@router.post(
    "/images",
    status_code=201,
    response_model=ApiResponse[ImageUploadResponse],
    dependencies=[
        Depends(check_upload_content_length),
        Depends(media_image_upload_idempotency_prepare),
    ],
)
async def upload_image(
    request: Request,
    x_idempotency_key: str | None = Header(default=None, alias="X-Idempotency-Key"),
    image: UploadFile = File(..., description="이미지 파일"),
    purpose: Literal["profile", "post"] = Query("post", description="profile | post"),
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_master_db),
):
    hit = getattr(request.state, MEDIA_UPLOAD_IDEMPOTENT_RESPONSE_ATTR, None)
    if hit is not None:
        delattr(request.state, MEDIA_UPLOAD_IDEMPOTENT_RESPONSE_ATTR)
        return hit
    try:
        data = await MediaService.upload_image(image, user.id, purpose, db=db)
        out = api_response(request, code=ApiCode.IMAGE_UPLOADED, data=data)
        await media_upload_idempotency_after_success(
            request, user.id, purpose, x_idempotency_key, out
        )
        return out
    except Exception:
        await media_upload_idempotency_after_failure(request, user.id, purpose, x_idempotency_key)
        raise


@router.delete("/images/{image_id}", status_code=204)
async def delete_image(
    image_id: int = Path(..., ge=1, description="이미지 ID"),
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_master_db),
):
    await MediaService.delete_image(image_id, user.id, db=db)
    return Response(status_code=204)
