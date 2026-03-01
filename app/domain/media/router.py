# 미디어 라우터. POST /media/images (로그인 필요, ?purpose=profile|post), POST /media/images/signup (비로그인, rate limit).
from typing import Literal

from fastapi import APIRouter, Depends, File, Path, Query, UploadFile
from sqlalchemy.orm import Session
from fastapi.responses import Response

from app.media import controller
from app.db import get_db
from app.common import ApiResponse
from app.core.dependencies import CurrentUser, get_current_user
from app.core.middleware import check_signup_upload_rate_limit

router = APIRouter(prefix="/media", tags=["media"])


@router.post("/images/signup", status_code=201, response_model=ApiResponse)
async def upload_image_signup(
    image: UploadFile = File(..., description="회원가입용 프로필 이미지"),
    _: None = Depends(check_signup_upload_rate_limit),
    db: Session = Depends(get_db),
):
    return await controller.upload_image_for_signup(file=image, db=db)


@router.post("/images", status_code=201, response_model=ApiResponse)
async def upload_image(
    image: UploadFile = File(..., description="이미지 파일"),
    purpose: Literal["profile", "post"] = Query("post", description="profile | post"),
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return await controller.upload_image(file=image, user=user, purpose=purpose, db=db)


@router.delete("/images/{image_id}", status_code=204)
def delete_image(
    image_id: int = Path(..., ge=1, description="이미지 ID"),
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    controller.delete_image(image_id=image_id, user=user, db=db)
    return Response(status_code=204)
