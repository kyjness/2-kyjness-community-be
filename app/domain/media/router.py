# 미디어 라우터. Router → Service. 예외는 전역 handler 처리.
from typing import Literal

from fastapi import APIRouter, Depends, File, Path, Query, UploadFile
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import (
    CurrentUser,
    check_upload_content_length,
    get_current_user,
    get_master_db,
)
from app.common import ApiCode, ApiResponse
from app.media.schema import ImageUploadResponse, SignupImageUploadData
from app.media.service import MediaService

router = APIRouter(prefix="/media", tags=["media"])


@router.post(
    "/images/signup",
    status_code=201,
    response_model=ApiResponse[SignupImageUploadData],
    dependencies=[Depends(check_upload_content_length)],
)
async def upload_image_signup(
    image: UploadFile = File(..., description="회원가입용 프로필 이미지"),
    db: AsyncSession = Depends(get_master_db),
):
    data = await MediaService.upload_image_for_signup(image, db=db)
    return ApiResponse(code=ApiCode.IMAGE_UPLOADED.value, data=data)


@router.post(
    "/images",
    status_code=201,
    response_model=ApiResponse[ImageUploadResponse],
    dependencies=[Depends(check_upload_content_length)],
)
async def upload_image(
    image: UploadFile = File(..., description="이미지 파일"),
    purpose: Literal["profile", "post"] = Query("post", description="profile | post"),
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_master_db),
):
    data = await MediaService.upload_image(image, user.id, purpose, db=db)
    return ApiResponse(code=ApiCode.IMAGE_UPLOADED.value, data=data)


@router.delete("/images/{image_id}", status_code=204)
async def delete_image(
    image_id: int = Path(..., ge=1, description="이미지 ID"),
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_master_db),
):
    await MediaService.delete_image(image_id, user.id, db=db)
    return Response(status_code=204)
