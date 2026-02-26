from typing import Optional

from fastapi import APIRouter, Cookie, Depends
from sqlalchemy.orm import Session
from starlette.responses import JSONResponse

from app.auth.schema import SignUpRequest, LoginRequest
from app.auth import controller
from app.core.config import settings
from app.core.database import get_db
from app.common import ApiResponse
from app.core.dependencies import CurrentUser, get_current_user
from app.core.middleware import check_login_rate_limit

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/signup", status_code=201, response_model=ApiResponse)
def signup(signup_data: SignUpRequest, db: Session = Depends(get_db)):
    return controller.signup_user(signup_data, db=db)


@router.post("/login", status_code=200, response_model=ApiResponse)
def login(login_data: LoginRequest, db: Session = Depends(get_db), _: None = Depends(check_login_rate_limit)):
    result, session_id = controller.login_user(login_data, db=db)
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


@router.post("/logout", status_code=200, response_model=ApiResponse)
def logout(session_id: Optional[str] = Cookie(None), db: Session = Depends(get_db)):
    result = controller.logout_user(session_id, db=db)
    response = JSONResponse(content=result)
    response.delete_cookie(key="session_id")
    return response


@router.get("/me", status_code=200, response_model=ApiResponse)
def get_session_user(user: CurrentUser = Depends(get_current_user)):
    return controller.get_session_user(user)
