# 사용자 라우터. GET/PATCH /users/me, PATCH /users/me/password.
from fastapi import APIRouter, Depends, Request
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.api.dependencies import (
    CurrentUser,
    get_current_user,
    get_master_db,
    get_slave_db,
    parse_availability_query,
)
from app.auth import controller as auth_controller
from app.common import ApiResponse
from app.users import controller
from app.users.schema import (
    AvailabilityData,
    UpdatePasswordRequest,
    UpdateUserRequest,
    UserAvailabilityQuery,
    UserProfileResponse,
)

router = APIRouter(prefix="/users", tags=["users"])


@router.get("/availability", status_code=200, response_model=ApiResponse[AvailabilityData])
def check_availability(
    query: UserAvailabilityQuery = Depends(parse_availability_query),
    db: Session = Depends(get_slave_db),
):
    return controller.check_availability(query, db=db)


@router.get("/me", status_code=200, response_model=ApiResponse[UserProfileResponse])
def get_me(
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_slave_db),
):
    return controller.get_me(user, db=db)


@router.patch("/me", status_code=200, response_model=ApiResponse[UserProfileResponse])
def update_me(
    user_data: UpdateUserRequest,
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_master_db),
):
    return controller.update_me(user=user, data=user_data, db=db)


@router.patch("/me/password", status_code=200, response_model=ApiResponse[None])
async def update_password(
    request: Request,
    password_data: UpdatePasswordRequest,
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_master_db),
):
    result = controller.update_password(user=user, data=password_data, db=db)
    redis = getattr(request.app.state, "redis", None)
    await auth_controller.revoke_refresh_for_user(user.id, redis)
    return result


@router.delete("/me", status_code=204)
async def delete_me(
    request: Request,
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_master_db),
):
    redis = getattr(request.app.state, "redis", None)
    if redis:
        await redis.delete(f"rt:{user.id}")
    controller.delete_me(user=user, db=db)
    return Response(status_code=204)
