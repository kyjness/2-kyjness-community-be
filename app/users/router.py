from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from fastapi.responses import Response

from app.users.schema import UpdateUserRequest, UpdatePasswordRequest, UserAvailabilityQuery
from app.users import controller
from app.core.database import get_db
from app.common import ApiResponse
from app.core.dependencies import CurrentUser, get_current_user, parse_availability_query

router = APIRouter(prefix="/users", tags=["users"])


@router.get("/availability", status_code=200, response_model=ApiResponse)
def check_availability(query: UserAvailabilityQuery = Depends(parse_availability_query), db: Session = Depends(get_db)):
    return controller.check_availability(query, db=db)


@router.get("/me", status_code=200, response_model=ApiResponse)
def get_me(user: CurrentUser = Depends(get_current_user)):
    return controller.get_me(user)


@router.patch("/me", status_code=200, response_model=ApiResponse)
def update_me(user_data: UpdateUserRequest, user: CurrentUser = Depends(get_current_user), db: Session = Depends(get_db)):
    return controller.update_me(user=user, data=user_data, db=db)


@router.patch("/me/password", status_code=200, response_model=ApiResponse)
def update_password(password_data: UpdatePasswordRequest, user: CurrentUser = Depends(get_current_user), db: Session = Depends(get_db)):
    return controller.update_password(user=user, data=password_data, db=db)


@router.delete("/me", status_code=204)
def withdraw_me(user: CurrentUser = Depends(get_current_user), db: Session = Depends(get_db)):
    controller.withdraw_me(user=user, db=db)
    return Response(status_code=204)
