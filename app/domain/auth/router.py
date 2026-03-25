# 인증 라우터. Router → Service. 예외는 전역 handler 처리. HTTP 응답·쿠키는 라우터 전담.

from fastapi import APIRouter, Depends, Request
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.responses import JSONResponse

from app.api.dependencies import CurrentUser, get_current_user, get_master_db
from app.auth.schema import (
    AccessTokenData,
    LoginRequest,
    LoginSuccessData,
    SignUpRequest,
)
from app.auth.service import AuthService
from app.common import ApiCode, ApiResponse, api_response, dump_api_response
from app.core.config import settings
from app.core.security import verify_access_token

router = APIRouter(prefix="/auth", tags=["auth"])


def _refresh_ttl_seconds() -> int:
    return settings.REFRESH_TOKEN_EXPIRE_DAYS * 86400


@router.post("/signup", status_code=201, response_model=ApiResponse[None])
async def signup(
    request: Request,
    signup_data: SignUpRequest,
    db: AsyncSession = Depends(get_master_db),
):
    redis: Redis | None = getattr(request.app.state, "redis", None)
    await AuthService.signup(signup_data, db=db, redis=redis)
    return api_response(request, code=ApiCode.SIGNUP_SUCCESS, data=None)


@router.post("/login", status_code=200, response_model=ApiResponse[LoginSuccessData])
async def login(
    request: Request,
    login_data: LoginRequest,
    db: AsyncSession = Depends(get_master_db),
):
    redis: Redis | None = getattr(request.app.state, "redis", None)
    ttl = _refresh_ttl_seconds()
    payload, refresh_token = await AuthService.login(
        login_data, db=db, redis=redis, refresh_ttl_seconds=ttl
    )
    response = JSONResponse(
        content=dump_api_response(request, code=ApiCode.LOGIN_SUCCESS, data=payload)
    )
    response.set_cookie(
        key=settings.REFRESH_TOKEN_COOKIE_NAME,
        value=refresh_token,
        httponly=True,
        secure=settings.COOKIE_SECURE,
        path="/",
        samesite="lax",
        max_age=ttl,
    )
    return response


@router.post("/logout", status_code=200, response_model=ApiResponse[None])
async def logout(
    request: Request,
    current_user: CurrentUser = Depends(get_current_user),
):
    refresh_token = request.cookies.get(settings.REFRESH_TOKEN_COOKIE_NAME)
    redis: Redis | None = getattr(request.app.state, "redis", None)
    auth = request.headers.get("Authorization") or ""
    access_token = auth[7:].strip() if auth.startswith("Bearer ") else ""
    access_payload = verify_access_token(access_token) if access_token else {}
    await AuthService.logout(
        user_id=current_user.id,
        refresh_token=refresh_token,
        access_token=access_token,
        access_payload=access_payload,
        redis=redis,
    )
    response = JSONResponse(
        content=dump_api_response(request, code=ApiCode.LOGOUT_SUCCESS, data=None)
    )
    response.delete_cookie(key=settings.REFRESH_TOKEN_COOKIE_NAME, path="/")
    return response


@router.post("/refresh", status_code=200, response_model=ApiResponse[AccessTokenData])
async def refresh(
    request: Request,
    db: AsyncSession = Depends(get_master_db),
):
    refresh_token = request.cookies.get(settings.REFRESH_TOKEN_COOKIE_NAME)
    redis: Redis | None = getattr(request.app.state, "redis", None)
    ttl = _refresh_ttl_seconds()
    data, new_refresh = await AuthService.refresh_tokens(refresh_token, redis, db, ttl)
    response = JSONResponse(
        content=dump_api_response(request, code=ApiCode.AUTH_SUCCESS, data=data)
    )
    response.set_cookie(
        key=settings.REFRESH_TOKEN_COOKIE_NAME,
        value=new_refresh,
        httponly=True,
        secure=settings.COOKIE_SECURE,
        path="/",
        samesite="lax",
        max_age=ttl,
    )
    return response
