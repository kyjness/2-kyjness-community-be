# app/routes/auth_route.py
from fastapi import APIRouter, HTTPException, Request, Body, Response, Cookie
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from typing import Optional
from pydantic import ValidationError
from app.auth.auth_scheme import SignUpRequest, LoginRequest
from app.auth.auth_controller import AuthController

router = APIRouter(prefix="/auth", tags=["auth"])

def get_client_identifier(request: Request) -> str:
    """클라이언트 식별자 생성 (Rate limiting용)"""
    # status code 429번
    #요청 과다
    client_host = request.client.host if request.client else "unknown"
    return client_host

# 회원가입
@router.post("/signup", status_code=201)
async def signup(request: Request, signup_data: Optional[SignUpRequest] = Body(None)):
    """회원가입 API"""
    try:
        # status code 400번
        # 빈 body 체크
        if signup_data is None:
            return JSONResponse(
                status_code=400,
                content={"code": "INVALID_REQUEST_BODY", "data": None}
            )
        
        # Controller 호출 (Rate limiting은 Controller 내부에서 처리)
        identifier = get_client_identifier(request)
        return AuthController.signup(
            email=signup_data.email,
            password=signup_data.password,
            password_confirm=signup_data.passwordConfirm,
            nickname=signup_data.nickname,
            profile_image_url=signup_data.profileImageUrl,
            identifier=identifier
        )
    except HTTPException as e:
        # status code: Controller에서 발생한 에러 코드 (400, 409, 429 등)
        # HTTPException의 detail이 dict인 경우 그대로 반환
        if isinstance(e.detail, dict):
            return JSONResponse(status_code=e.status_code, content=e.detail)
        raise
    except RequestValidationError as e:
        # status code 400번
        # FastAPI의 RequestValidationError 처리 (빈 body, 잘못된 형식 등)
        return JSONResponse(
            status_code=400,
            content={"code": "INVALID_REQUEST_BODY", "data": None}
        )
    except ValidationError as e:
        # status code 400번
        # Pydantic 검증 오류 처리
        errors = e.errors()
        if errors:
            first_error = errors[0]
            field = first_error.get("loc", [])
            
            if "email" in str(field).lower():
                return JSONResponse(
                    status_code=400,
                    content={"code": "INVALID_EMAIL_FORMAT", "data": None}
                )
            elif "password" in str(field).lower() or "passwordconfirm" in str(field).lower():
                return JSONResponse(
                    status_code=400,
                    content={"code": "INVALID_PASSWORD_FORMAT", "data": None}
                )
            elif "nickname" in str(field).lower():
                return JSONResponse(
                    status_code=400,
                    content={"code": "INVALID_NICKNAME_FORMAT", "data": None}
                )
        
        return JSONResponse(
            status_code=400,
            content={"code": "INVALID_REQUEST_BODY", "data": None}
        )
    except Exception as e:
        # status code 500번
        # 예상치 못한 모든 에러
        return JSONResponse(
            status_code=500,
            content={"code": "INTERNAL_SERVER_ERROR", "data": None}
        )

# 로그인 (쿠키-세션 방식)
@router.post("/login", status_code=200)
async def login(request: Request, response: Response, login_data: Optional[LoginRequest] = None):
    """로그인 API (쿠키-세션 방식)"""
    try:
        # status code 400번
        # 빈 body 체크
        if login_data is None:
            return JSONResponse(
                status_code=400,
                content={"code": "INVALID_REQUEST_BODY", "data": None}
            )
        
        # Controller 호출 (Rate limiting은 Controller 내부에서 처리)
        identifier = get_client_identifier(request)
        result = AuthController.login(
            email=login_data.email,
            password=login_data.password,
            identifier=identifier
        )
        
        # 세션 ID를 쿠키에 설정 (authToken은 API 명세서에 따라 응답에 포함)
        session_id = result["data"]["authToken"]
        response.set_cookie(
            key="session_id",
            value=session_id,
            httponly=True,  # XSS 공격 방지
            secure=False,  # HTTPS 사용 시 True로 변경
            samesite="lax",  # CSRF 공격 방지
            max_age=86400  # 24시간 (초 단위)
        )
        
        # status code 200번(로그인 성공)
        # 응답 반환 (authToken은 명세서에 따라 포함)
        return result
    except HTTPException as e:
        # status code: Controller에서 발생한 에러 코드 (400, 401, 429 등)
        # HTTPException의 detail이 dict인 경우 그대로 반환
        if isinstance(e.detail, dict):
            return JSONResponse(status_code=e.status_code, content=e.detail)
        raise
    except ValidationError as e:
        # status code 400번
        # Pydantic 검증 오류 처리
        errors = e.errors()
        if errors:
            first_error = errors[0]
            field = first_error.get("loc", [])
            
            if "email" in str(field).lower():
                return JSONResponse(
                    status_code=400,
                    content={"code": "INVALID_EMAIL_FORMAT", "data": None}
                )
            elif "password" in str(field).lower():
                return JSONResponse(
                    status_code=400,
                    content={"code": "INVALID_PASSWORD_FORMAT", "data": None}
                )
        
        return JSONResponse(
            status_code=400,
            content={"code": "INVALID_REQUEST_BODY", "data": None}
        )
    except Exception as e:
        # status code 500번
        # 예상치 못한 모든 에러
        return JSONResponse(
            status_code=500,
            content={"code": "INTERNAL_SERVER_ERROR", "data": None}
        )

# 로그아웃 (쿠키-세션 방식)
@router.post("/logout", status_code=200)
async def logout(response: Response, session_id: Optional[str] = Cookie(None)):
    """로그아웃 API (쿠키-세션 방식)"""
    try:
        # Controller 호출
        result = AuthController.logout(session_id)
        
        # 쿠키 삭제
        response.delete_cookie(key="session_id")
        
        # status code 200번(로그아웃 성공)
        return result
    except HTTPException as e:
        # status code: Controller에서 발생한 에러 코드 (401 등)
        # HTTPException의 detail이 dict인 경우 그대로 반환
        if isinstance(e.detail, dict):
            return JSONResponse(status_code=e.status_code, content=e.detail)
        raise
    except Exception as e:
        # status code 500번
        # 예상치 못한 모든 에러
        return JSONResponse(
            status_code=500,
            content={"code": "INTERNAL_SERVER_ERROR", "data": None}
        )

# 로그인 상태 체크 (쿠키-세션 방식)
@router.get("/me", status_code=200)
async def get_me(session_id: Optional[str] = Cookie(None)):
    """로그인 상태 체크 API (쿠키-세션 방식)"""
    try:
        # Controller 호출
        # status code 200번(로그인 상태 체크 성공)
        return AuthController.get_me(session_id)
    except HTTPException as e:
        # status code: Controller에서 발생한 에러 코드 (401 등)
        # HTTPException의 detail이 dict인 경우 그대로 반환
        if isinstance(e.detail, dict):
            return JSONResponse(status_code=e.status_code, content=e.detail)
        raise
    except Exception as e:
        # status code 500번
        # 예상치 못한 모든 에러
        return JSONResponse(
            status_code=500,
            content={"code": "INTERNAL_SERVER_ERROR", "data": None}
        )
