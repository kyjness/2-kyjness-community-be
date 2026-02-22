# app/media/router.py

from typing import Literal

from fastapi import APIRouter, Depends, File, Path, Query, UploadFile
from fastapi.responses import Response

from app.media import controller
from app.core.dependencies import get_current_user
from app.core.response import ApiResponse

router = APIRouter(prefix="/media", tags=["media"])


@router.post("/images", status_code=201, response_model=ApiResponse)
async def upload_image(image: UploadFile = File(..., description="이미지 파일"), image_type: Literal["profile", "post"] = Query("post", alias="type", description="profile/post"), user_id: int = Depends(get_current_user)):
    return await controller.upload_image(file=image, user_id=user_id, folder=image_type)

@router.delete("/images/{image_id}", status_code=204)
async def withdraw_image(image_id: int = Path(..., description="이미지 ID"), user_id: int = Depends(get_current_user)):
    controller.withdraw_image(image_id=image_id, user_id=user_id)
    return Response(status_code=204)
