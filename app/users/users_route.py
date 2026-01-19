# app/users/users_route.py
from fastapi import APIRouter, Query, UploadFile, File, Depends, Path
from fastapi.responses import Response
from typing import Optional
from app.users.users_scheme import UpdateUserRequest, UpdatePasswordRequest
from app.users import users_controller
from app.core.dependencies import get_current_user

router = APIRouter(prefix="/users", tags=["users"])

# 프로필이미지 업로드
@router.post("/{user_id}/profile-image", status_code=201)
async def upload_profile_image(
    user_id: int = Path(..., ge=1, description="사용자 ID"),
    profileImage: Optional[UploadFile] = File(None, description="프로필 이미지 파일 (.jpg)"),
    authenticated_user_id: int = Depends(get_current_user)
):
    """프로필 이미지 업로드 API"""
    return await users_controller.upload_profile_image(
        user_id=user_id,
        authenticated_user_id=authenticated_user_id,
        profile_image=profileImage
    )

# 이메일 중복 체크 (구체적 경로이므로 경로 파라미터보다 먼저 정의)
@router.get("/check-email", status_code=200)
async def check_email(email: Optional[str] = Query(None, description="이메일")):
    """이메일 중복 체크 API"""
    return users_controller.check_email(email=email)

# 닉네임 중복 체크 (구체적 경로이므로 경로 파라미터보다 먼저 정의)
@router.get("/check-nickname", status_code=200)
async def check_nickname(nickname: Optional[str] = Query(None, description="닉네임")):
    """닉네임 중복 체크 API"""
    return users_controller.check_nickname(nickname=nickname)

# 내 정보 조회
@router.get("/{user_id}", status_code=200)
async def get_user(user_id: int = Path(..., ge=1, description="사용자 ID"), authenticated_user_id: int = Depends(get_current_user)):
    """내 정보 조회 API"""
    return users_controller.get_user(user_id=user_id, authenticated_user_id=authenticated_user_id)

# 내 정보 수정
@router.patch("/{user_id}", status_code=200)
async def update_user(user_data: UpdateUserRequest, user_id: int = Path(..., ge=1, description="사용자 ID"), authenticated_user_id: int = Depends(get_current_user)):
    """내 정보 수정 API"""
    return users_controller.update_user(
        user_id=user_id,
        authenticated_user_id=authenticated_user_id,
        nickname=user_data.nickname,
        profile_image_url=user_data.profileImageUrl
    )

# 비밀번호 변경
@router.patch("/{user_id}/password", status_code=200)
async def update_password(password_data: UpdatePasswordRequest, user_id: int = Path(..., ge=1, description="사용자 ID"), authenticated_user_id: int = Depends(get_current_user)):
    """비밀번호 변경 API"""
    return users_controller.update_password(
        user_id=user_id,
        authenticated_user_id=authenticated_user_id,
        current_password=password_data.currentPassword,
        new_password=password_data.newPassword
    )

# 회원 탈퇴
@router.delete("/{user_id}", status_code=204)
async def withdraw_user(user_id: int = Path(..., ge=1, description="사용자 ID"), authenticated_user_id: int = Depends(get_current_user)):
    """회원 탈퇴 API"""
    users_controller.withdraw_user(user_id=user_id, authenticated_user_id=authenticated_user_id)
    
    # status code 204번(탈퇴 성공) - 응답 본문 없음
    return Response(status_code=204)
