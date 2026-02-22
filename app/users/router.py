# app/users/router.py

from fastapi import APIRouter, Depends
from fastapi.responses import Response

from app.users.schema import UpdateUserRequest, UpdatePasswordRequest, UserAvailabilityQuery
from app.users import controller
from app.core.dependencies import get_current_user, parse_availability_query
from app.core.response import ApiResponse

router = APIRouter(prefix="/users", tags=["users"])


@router.get("/availability", status_code=200, response_model=ApiResponse)
async def check_availability(query: UserAvailabilityQuery = Depends(parse_availability_query)):
    return controller.check_availability(query)

@router.get("/me", status_code=200, response_model=ApiResponse)
async def get_me(user_id: int = Depends(get_current_user)):
    return controller.get_me(user_id=user_id)

@router.patch("/me", status_code=200, response_model=ApiResponse)
async def update_me(user_data: UpdateUserRequest, user_id: int = Depends(get_current_user)):
    return controller.update_me(user_id=user_id, data=user_data)

@router.patch("/me/password", status_code=200, response_model=ApiResponse)
async def update_password(password_data: UpdatePasswordRequest, user_id: int = Depends(get_current_user)):
    return controller.update_password(user_id=user_id, data=password_data)

@router.delete("/me", status_code=204)
async def withdraw_me(user_id: int = Depends(get_current_user)):
    controller.withdraw_me(user_id=user_id)
    return Response(status_code=204)
