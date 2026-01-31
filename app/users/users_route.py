# app/users/users_route.py
from fastapi import APIRouter, Query, UploadFile, File, Depends, Path
from fastapi.responses import Response
from typing import Optional
from app.users.users_schema import UpdateUserRequest, UpdatePasswordRequest
from app.users import users_controller
from app.core.dependencies import get_current_user, require_same_user

router = APIRouter(prefix="/users", tags=["users"])

@router.post("/{user_id}/profile-image", status_code=201)
async def upload_profile_image(
    user_id: int = Path(..., description="사용자 ID"),
    profileImage: Optional[UploadFile] = File(None, description="프로필 이미지 파일 (.jpg)"),
    _: int = Depends(require_same_user),
):
    return await users_controller.upload_profile_image(user_id=user_id, profile_image=profileImage)

@router.get("/check-email", status_code=200)
async def check_email(email: Optional[str] = Query(None, description="이메일")):
    return users_controller.check_email(email=email)

@router.get("/check-nickname", status_code=200)
async def check_nickname(nickname: Optional[str] = Query(None, description="닉네임")):
    return users_controller.check_nickname(nickname=nickname)

@router.get("/{user_id}", status_code=200)
async def get_user(
    user_id: int = Path(..., description="사용자 ID"),
    _: int = Depends(require_same_user),
):
    return users_controller.get_user(user_id=user_id)

@router.patch("/{user_id}", status_code=200)
async def update_user(
    user_data: UpdateUserRequest,
    user_id: int = Path(..., description="사용자 ID"),
    _: int = Depends(require_same_user),
):
    return users_controller.update_user(
        user_id=user_id,
        nickname=user_data.nickname,
        profile_image_url=user_data.profileImageUrl,
    )

@router.patch("/{user_id}/password", status_code=200)
async def update_password(
    password_data: UpdatePasswordRequest,
    user_id: int = Path(..., description="사용자 ID"),
    _: int = Depends(require_same_user),
):
    return users_controller.update_password(
        user_id=user_id,
        current_password=password_data.currentPassword,
        new_password=password_data.newPassword,
    )

@router.delete("/{user_id}", status_code=204)
async def withdraw_user(
    user_id: int = Path(..., description="사용자 ID"),
    _: int = Depends(require_same_user),
):
    users_controller.withdraw_user(user_id=user_id)
    return Response(status_code=204)
