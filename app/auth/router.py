# app/auth/router.py

from typing import Optional

from fastapi import APIRouter, Cookie, Depends
from starlette.responses import JSONResponse

from app.auth.schema import SignUpRequest, LoginRequest
from app.auth import controller
from app.auth.util import set_cookie
from app.core.dependencies import get_current_user
from app.core.rate_limit import check_login_rate_limit
from app.core.response import ApiResponse

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/signup", status_code=201, response_model=ApiResponse)
async def signup(signup_data: SignUpRequest):
    return controller.signup_user(signup_data)

@router.post("/login", status_code=200, response_model=ApiResponse)
async def login(login_data: LoginRequest, _: None = Depends(check_login_rate_limit)):
    result, session_id = controller.login_user(login_data)
    response = JSONResponse(content=result)
    set_cookie(response, session_id)
    return response

@router.post("/logout", status_code=200, response_model=ApiResponse)
async def logout(session_id: Optional[str] = Cookie(None)):
    result = controller.logout_user(session_id)
    response = JSONResponse(content=result)
    response.delete_cookie(key="session_id")
    return response

@router.get("/me", status_code=200, response_model=ApiResponse)
async def get_session_user(user_id: int = Depends(get_current_user)):
    return controller.get_session_user(user_id)
