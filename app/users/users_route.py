# app/users/users_route.py
# REST: 중복 체크 = GET /users?email=...|?nickname=... / 보호된 API = /users/me. 입력 검증은 DTO(Pydantic)에서.
from fastapi import APIRouter, Query, UploadFile, File, Depends
from fastapi.responses import Response
from typing import Optional
from pydantic import ValidationError

from app.users.users_schema import UpdateUserRequest, UpdatePasswordRequest, CheckUserExistsQuery
from app.users import users_controller
from app.core.dependencies import get_current_user
from app.core.response import raise_http_error

router = APIRouter(prefix="/users", tags=["users"])


def get_check_user_query(
    email: Optional[str] = Query(None),
    nickname: Optional[str] = Query(None),
) -> CheckUserExistsQuery:
    """Query → DTO. 검증 실패 시 400 INVALID_REQUEST (DTO가 exactly-one 검증)."""
    try:
        return CheckUserExistsQuery(email=email, nickname=nickname)
    except ValidationError:
        raise_http_error(400, "INVALID_REQUEST")


# GET /users?email=... 또는 ?nickname=... (중복 체크). 입력 검증은 DTO.
@router.get("", status_code=200)
async def get_users_exists(query: CheckUserExistsQuery = Depends(get_check_user_query)):
    return users_controller.check_user_exists(query=query)

# --- /users/me: 현재 로그인한 사용자 전용 (Path user_id·require_same_user 제거) ---
@router.get("/me", status_code=200)
async def get_me(user_id: int = Depends(get_current_user)):
    return users_controller.get_user(user_id=user_id)

@router.patch("/me", status_code=200)
async def update_me(
    user_data: UpdateUserRequest,
    user_id: int = Depends(get_current_user),
):
    return users_controller.update_user(
        user_id=user_id,
        nickname=user_data.nickname,
        profile_image_url=user_data.profileImageUrl,
    )

@router.patch("/me/password", status_code=200)
async def update_me_password(
    password_data: UpdatePasswordRequest,
    user_id: int = Depends(get_current_user),
):
    return users_controller.update_password(
        user_id=user_id,
        current_password=password_data.currentPassword,
        new_password=password_data.newPassword,
    )

# 라우터: 요청 수신 → 컨트롤러 호출만. 파일 정책(필수/확장자/MIME/크기)은 컨트롤러에서 검증.
@router.post("/me/profile-image", status_code=201)
async def upload_me_profile_image(
    profileImage: UploadFile = File(description="프로필 이미지"),
    user_id: int = Depends(get_current_user),
):
    return await users_controller.upload_profile_image(user_id=user_id, profile_image=profileImage)

@router.delete("/me", status_code=204)
async def withdraw_me(user_id: int = Depends(get_current_user)):
    users_controller.withdraw_user(user_id=user_id)
    return Response(status_code=204)
