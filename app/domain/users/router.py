# 사용자 라우터. Router → Service. 예외는 전역 handler 처리.
from fastapi import APIRouter, Depends, Request
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import (
    CurrentUser,
    get_current_user,
    get_master_db,
    get_slave_db,
    parse_availability_query,
)
from app.auth.service import AuthService
from app.common import ApiCode, ApiResponse
from app.users.schema import (
    AvailabilityData,
    BlocksData,
    BlockToggleResponse,
    UpdatePasswordRequest,
    UpdateUserRequest,
    UserAvailabilityQuery,
    UserProfileResponse,
)
from app.users.service import UserService

router = APIRouter(prefix="/users", tags=["users"])


@router.get("/availability", status_code=200, response_model=ApiResponse[AvailabilityData])
async def check_availability(
    query: UserAvailabilityQuery = Depends(parse_availability_query),
    db: AsyncSession = Depends(get_slave_db),
):
    data = await UserService.check_availability(query, db=db)
    return ApiResponse(code=ApiCode.OK, data=data)


@router.get("/me", status_code=200, response_model=ApiResponse[UserProfileResponse])
async def get_me(
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_slave_db),
):
    data = await UserService.get_user_profile(user.id, db=db)
    return ApiResponse(code=ApiCode.USER_RETRIEVED, data=data)


@router.patch("/me", status_code=200, response_model=ApiResponse[UserProfileResponse])
async def update_me(
    user_data: UpdateUserRequest,
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_master_db),
):
    data = await UserService.update_user_profile(user.id, user_data, db=db)
    return ApiResponse(code=ApiCode.USER_UPDATED, data=data)


@router.patch("/me/password", status_code=200, response_model=ApiResponse[None])
async def update_password(
    request: Request,
    password_data: UpdatePasswordRequest,
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_master_db),
):
    await UserService.update_password(user.id, password_data, db=db)
    redis = getattr(request.app.state, "redis", None)
    await AuthService.revoke_refresh_for_user(user.id, redis)
    return ApiResponse(code=ApiCode.PASSWORD_UPDATED, data=None)


@router.delete("/me", status_code=204)
async def delete_me(
    request: Request,
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_master_db),
):
    redis = getattr(request.app.state, "redis", None)
    await AuthService.revoke_refresh_for_user(user.id, redis)
    await UserService.delete_user(user.id, db=db)
    return Response(status_code=204)


@router.get("/me/blocks", status_code=200, response_model=ApiResponse[BlocksData])
async def get_my_blocks(
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_slave_db),
):
    data = await UserService.get_blocked_list(user.id, db=db)
    return ApiResponse(code=ApiCode.BLOCKS_RETRIEVED, data=data)


@router.post(
    "/{target_user_id}/block",
    status_code=200,
    response_model=ApiResponse[BlockToggleResponse],
)
async def toggle_block_user(
    target_user_id: int,
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_master_db),
):
    """유저 차단/차단해제 토글. 이미 차단된 경우 해제."""
    is_blocked = await UserService.toggle_block_user(user.id, target_user_id, db=db)
    return ApiResponse(
        code=ApiCode.OK,
        data=BlockToggleResponse(blocked=is_blocked),
    )
