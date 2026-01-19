# app/auth/auth_route.py
from fastapi import APIRouter, Response, Cookie, Depends
from typing import Optional
from app.auth.auth_scheme import SignUpRequest, LoginRequest
from app.auth import auth_controller
from app.auth.dependencies import get_current_user

router = APIRouter(prefix="/auth", tags=["auth"])

# 회원가입
@router.post("/signup", status_code=201)
async def signup(signup_data: SignUpRequest):
    """회원가입 API"""
    return auth_controller.signup(
        email=signup_data.email,
        password=signup_data.password,
        password_confirm=signup_data.passwordConfirm,
        nickname=signup_data.nickname,
        profile_image_url=signup_data.profileImageUrl
    )

# 로그인 (쿠키-세션 방식)
@router.post("/login", status_code=200)
async def login(login_data: LoginRequest, response: Response):
    """로그인 API (쿠키-세션 방식)"""
    result = auth_controller.login(
        email=login_data.email,
        password=login_data.password
    )
    
    # 세션 ID를 쿠키에 설정 (HTTP 응답 처리)
    session_id = result["data"]["authToken"]
    response.set_cookie(
        key="session_id",
        value=session_id,
        httponly=True,  # XSS 공격 방지
        secure=False,  # HTTPS 사용 시 True로 변경
        samesite="lax",  # CSRF 공격 방지
        max_age=86400  # 24시간 (초 단위)
    )
    
    return result

# 로그아웃 (쿠키-세션 방식)
@router.post("/logout", status_code=200)
async def logout(response: Response, session_id: Optional[str] = Cookie(None), user_id: int = Depends(get_current_user)):
    """로그아웃 API (쿠키-세션 방식)"""
    result = auth_controller.logout(session_id)
    
    # 쿠키 삭제 (HTTP 응답 처리)
    response.delete_cookie(key="session_id")
    
    return result

# 로그인 상태 체크 (쿠키-세션 방식)
@router.get("/me", status_code=200)
async def get_me(user_id: int = Depends(get_current_user)):
    """로그인 상태 체크 API (쿠키-세션 방식)"""
    return auth_controller.get_me(user_id)
