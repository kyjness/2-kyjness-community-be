# app/auth/router.py
"""인증 라우트. 바디 검증은 FastAPI(Pydantic), 비즈니스 로직은 controller."""

from typing import Optional

from fastapi import APIRouter, Cookie, Depends
from starlette.responses import JSONResponse

from app.auth.schema import SignUpRequest, LoginRequest
from app.auth import controller
from app.core.config import settings
from app.core.dependencies import get_current_user
from app.core.rate_limit import check_login_rate_limit
from app.core.response import ApiResponse

router = APIRouter(prefix="/auth", tags=["auth"])


def _set_login_cookie(response: JSONResponse, session_id: str) -> None:
    response.set_cookie(
        key="session_id",
        value=session_id,
        httponly=True,
        secure=settings.COOKIE_SECURE,
        path="/",
        samesite="lax",
        max_age=settings.SESSION_EXPIRY_TIME,
    )


@router.post("/signup", status_code=201, response_model=ApiResponse)
async def signup(signup_data: SignUpRequest):
    """회원가입. JSON: email, password, nickname, profileImageId(선택)."""
    return controller.signup(signup_data)


@router.post("/login", status_code=200, response_model=ApiResponse)
async def login(
    login_data: LoginRequest,
    _: None = Depends(check_login_rate_limit),
):
    """로그인. 세션 ID는 Set-Cookie로만 전달. IP당 분당 5회 제한."""
    result, session_id = controller.login(login_data)
    response = JSONResponse(content=result)
    _set_login_cookie(response, session_id)
    return response


@router.post("/logout", status_code=200, response_model=ApiResponse)
async def logout(session_id: Optional[str] = Cookie(None)):
    """로그아웃. 세션 삭제 후 쿠키 제거. 인증 없이 호출 가능."""
    result = controller.logout(session_id)
    response = JSONResponse(content=result)
    response.delete_cookie(key="session_id")
    return response


@router.get("/me", status_code=200, response_model=ApiResponse)
async def get_session_user(user_id: int = Depends(get_current_user)):
    """세션 유효성 + 최소 사용자 정보. 프로필 전체는 GET /v1/users/me."""
    return controller.get_session_user(user_id)
