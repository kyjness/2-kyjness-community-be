# app/auth/auth_route.py
from fastapi import APIRouter, Cookie, Depends
from starlette.responses import JSONResponse
from typing import Optional

from app.auth.auth_schema import SignUpRequest, LoginRequest
from app.auth import auth_controller
from app.core.config import settings
from app.core.dependencies import get_current_user
from app.core.rate_limit import check_login_rate_limit
from app.core.response import ApiResponse

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/signup", status_code=201, response_model=ApiResponse)
async def signup(signup_data: SignUpRequest):
    """회원가입. 프로필 이미지는 먼저 POST /v1/media/images 로 업로드 후 profileImageId 전달."""
    return auth_controller.signup(signup_data)


@router.post("/login", status_code=200, response_model=ApiResponse)
async def login(
    login_data: LoginRequest,
    _: None = Depends(check_login_rate_limit),
):
    """로그인 — 세션 ID는 Set-Cookie로만 전달. IP당 분당 5회 제한."""
    result, session_id = auth_controller.login(login_data)
    response = JSONResponse(content=result)
    response.set_cookie(
        key="session_id",
        value=session_id,
        httponly=True,
        secure=settings.COOKIE_SECURE,
        path="/",
        samesite="lax",
        max_age=settings.SESSION_EXPIRY_TIME,
    )
    return response


# 로그아웃 (쿠키-세션 방식). 인증 없이 호출 가능 — 만료된 세션이어도 쿠키 제거 가능
@router.post("/logout", status_code=200, response_model=ApiResponse)
async def logout(session_id: Optional[str] = Cookie(None)):
    """로그아웃 API — 세션 삭제 후 쿠키 제거. 세션 없/만료여도 쿠키는 삭제함."""
    result = auth_controller.logout(session_id)
    response = JSONResponse(content=result)
    response.delete_cookie(key="session_id")
    return response


@router.get("/me", status_code=200, response_model=ApiResponse)
async def get_me(user_id: int = Depends(get_current_user)):
    """세션 검증·로그인 여부. 프로필 조회/수정은 GET /v1/users/me."""
    return auth_controller.get_me(user_id)

