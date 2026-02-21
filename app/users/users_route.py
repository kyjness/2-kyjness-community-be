# app/users/users_route.py
# /v1/users: availability, /users/me (조회·수정·탈퇴·비밀번호). 입력 검증은 DTO.
from fastapi import APIRouter, Query, Depends
from fastapi.responses import Response
from typing import Optional
from pydantic import ValidationError

from app.users.users_schema import UpdateUserRequest, UpdatePasswordRequest, UserAvailabilityQuery
from app.users import users_controller
from app.core.codes import ApiCode
from app.core.dependencies import get_current_user
from app.core.response import ApiResponse, raise_http_error

router = APIRouter(prefix="/users", tags=["users"])


def parse_availability_query(
    email: Optional[str] = Query(None, description="이메일"),
    nickname: Optional[str] = Query(None, description="닉네임"),
) -> UserAvailabilityQuery:
    """Query 파라미터를 파싱해 UserAvailabilityQuery 생성. 최소 하나 필수. 검증 실패 시 400."""
    try:
        return UserAvailabilityQuery(email=email, nickname=nickname)
    except ValidationError:
        raise_http_error(400, ApiCode.INVALID_REQUEST)


@router.get("/availability", status_code=200, response_model=ApiResponse)
async def get_availability(query: UserAvailabilityQuery = Depends(parse_availability_query)):
    """이메일·닉네임 가용 여부. 요청한 항목만 반환. 사용자 정보 노출 없음."""
    return users_controller.check_availability(query)


@router.get("/me", status_code=200, response_model=ApiResponse)
async def get_me(user_id: int = Depends(get_current_user)):
    """내 프로필 조회. 로그인 여부만 확인할 때는 GET /v1/auth/me 사용."""
    return users_controller.get_user_profile(user_id=user_id)


@router.patch("/me", status_code=200, response_model=ApiResponse)
async def update_me(
    user_data: UpdateUserRequest,
    user_id: int = Depends(get_current_user),
):
    return users_controller.update_user(user_id=user_id, data=user_data)


@router.patch("/me/password", status_code=200, response_model=ApiResponse)
async def update_me_password(
    password_data: UpdatePasswordRequest,
    user_id: int = Depends(get_current_user),
):
    return users_controller.update_password(user_id=user_id, data=password_data)


@router.delete("/me", status_code=204)
async def withdraw_me(user_id: int = Depends(get_current_user)):
    users_controller.withdraw_user(user_id=user_id)
    return Response(status_code=204)
