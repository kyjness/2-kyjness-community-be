# 인증 라우터. Router → Service. 예외는 전역 handler 처리. HTTP 응답·쿠키는 라우터 전담.
from typing import Optional

from fastapi import APIRouter, Depends, Request
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.responses import JSONResponse

from app.api.dependencies import get_master_db
from app.auth.schema import (
    AccessTokenData,
    LoginSuccessData,
    LoginRequest,
    SignUpRequest,
)
from app.auth.service import AuthService
from app.common import ApiCode, ApiResponse
from app.core.config import settings

router = APIRouter(prefix="/auth", tags=["auth"])


def _refresh_ttl_seconds() -> int:
    return settings.REFRESH_TOKEN_EXPIRE_DAYS * 86400


@router.post("/signup", status_code=201, response_model=ApiResponse[None])
async def signup(
    signup_data: SignUpRequest,
    db: AsyncSession = Depends(get_master_db),
):
    await AuthService.signup(signup_data, db=db)
    return ApiResponse(code=ApiCode.SIGNUP_SUCCESS.value, data=None)


@router.post("/login", status_code=200, response_model=ApiResponse[LoginSuccessData])
async def login(
    request: Request,
    login_data: LoginRequest,
    db: AsyncSession = Depends(get_master_db),
):
    redis: Optional[Redis] = getattr(request.app.state, "redis", None)
    ttl = _refresh_ttl_seconds()
    payload, refresh_token = await AuthService.login(
        login_data, db=db, redis=redis, refresh_ttl_seconds=ttl
    )
    response = JSONResponse(
        content=ApiResponse(code=ApiCode.LOGIN_SUCCESS.value, data=payload).model_dump(
            by_alias=True
        )
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
async def logout(request: Request):
    refresh_token = request.cookies.get(settings.REFRESH_TOKEN_COOKIE_NAME)
    redis: Optional[Redis] = getattr(request.app.state, "redis", None)
    await AuthService.logout(refresh_token, redis=redis)
    result = ApiResponse(code=ApiCode.LOGOUT_SUCCESS.value, data=None)
    response = JSONResponse(content=result.model_dump(by_alias=True))
    response.delete_cookie(key=settings.REFRESH_TOKEN_COOKIE_NAME, path="/")
    return response


@router.post("/refresh", status_code=200, response_model=ApiResponse[AccessTokenData])
async def refresh(
    request: Request,
    db: AsyncSession = Depends(get_master_db),
):
    refresh_token = request.cookies.get(settings.REFRESH_TOKEN_COOKIE_NAME)
    redis: Optional[Redis] = getattr(request.app.state, "redis", None)
    data = await AuthService.refresh_tokens(refresh_token, redis, db)
    result = ApiResponse(code=ApiCode.AUTH_SUCCESS.value, data=data)
    return JSONResponse(content=result.model_dump(by_alias=True))
