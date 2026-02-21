# app/media/router.py
"""이미지 업로드/삭제 라우트."""

from typing import Literal, Optional

from fastapi import APIRouter, Depends, File, Path, Query, UploadFile

from app.media import controller
from app.core.dependencies import get_current_user, get_current_user_optional
from app.core.response import ApiResponse

router = APIRouter(prefix="/media", tags=["media"])


@router.delete("/images/{image_id}", status_code=204)
async def withdraw_image(
    image_id: int = Path(..., description="이미지 ID"),
    user_id: int = Depends(get_current_user),
):
    """이미지 철회 (deleted_at 저장). 업로더 본인만 가능."""
    controller.withdraw_image(image_id=image_id, user_id=user_id)


@router.post("/images", status_code=201, response_model=ApiResponse)
async def upload_image(
    image: UploadFile = File(..., description="이미지 파일"),
    image_type: Literal["profile", "post"] = Query("post", alias="type", description="profile/post"),
    user_id: Optional[int] = Depends(get_current_user_optional),
):
    """이미지 업로드. profile/post 타입에 따라 저장 경로 분기."""
    return await controller.upload_image(file=image, user_id=user_id, folder=image_type)
