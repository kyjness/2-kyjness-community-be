# 인증 라우터. 로그인·로그아웃·리프레시(JWT)·회원가입·GET /auth/me.
from typing import Optional

from fastapi import APIRouter, Depends, Request
from redis.asyncio import Redis
from sqlalchemy.orm import Session
from starlette.responses import JSONResponse

from app.auth import controller
from app.auth.schema import AccessTokenData, LoginSuccessData, SignUpRequest, LoginRequest, SessionUserResponse
from app.common import ApiResponse
from app.core.config import settings
from app.api.dependencies import CurrentUser, get_current_user, get_master_db

router = APIRouter(prefix="/auth", tags=["auth"])

_REFRESH_KEY_PREFIX = "rt:"


def _refresh_ttl_seconds() -> int:
    return settings.REFRESH_TOKEN_EXPIRE_DAYS * 86400


@router.post("/signup", status_code=201, response_model=ApiResponse[None])
def signup(
    signup_data: SignUpRequest,
    db: Session = Depends(get_master_db),
):
    return controller.signup_user(signup_data, db=db)


@router.post("/login", status_code=200, response_model=ApiResponse[LoginSuccessData])
async def login(
    request: Request,
    login_data: LoginRequest,
    db: Session = Depends(get_master_db),
):
    result, access_token, refresh_token, user_id = controller.login_user(login_data, db=db)
    response = JSONResponse(content=result.model_dump(by_alias=True))
    response.set_cookie(
        key=settings.REFRESH_TOKEN_COOKIE_NAME,
        value=refresh_token,
        httponly=True,
        secure=settings.COOKIE_SECURE,
        path="/",
        samesite="lax",
        max_age=_refresh_ttl_seconds(),
    )
    redis: Optional[Redis] = getattr(request.app.state, "redis", None)
    if redis:
        await redis.set(f"{_REFRESH_KEY_PREFIX}{user_id}", refresh_token, ex=_refresh_ttl_seconds())
    return response


@router.post("/logout", status_code=200, response_model=ApiResponse[None])
async def logout(request: Request):
    refresh_token = request.cookies.get(settings.REFRESH_TOKEN_COOKIE_NAME)
    redis: Optional[Redis] = getattr(request.app.state, "redis", None)
    result = await controller.logout_user(refresh_token, redis)
    response = JSONResponse(content=result.model_dump(by_alias=True))
    response.delete_cookie(key=settings.REFRESH_TOKEN_COOKIE_NAME, path="/")
    return response


@router.post("/refresh", status_code=200, response_model=ApiResponse[AccessTokenData])
async def refresh(
    request: Request,
    db: Session = Depends(get_master_db),
):
    refresh_token = request.cookies.get(settings.REFRESH_TOKEN_COOKIE_NAME)
    redis: Optional[Redis] = getattr(request.app.state, "redis", None)
    result, _ = await controller.refresh_tokens(refresh_token, redis, db)
    return JSONResponse(content=result.model_dump(by_alias=True))


@router.get("/me", status_code=200, response_model=ApiResponse[SessionUserResponse])
def get_session_user(user: CurrentUser = Depends(get_current_user)):
    return controller.get_session_user(user)
