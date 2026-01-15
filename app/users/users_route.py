# app/users/users_route.py
from fastapi import APIRouter, HTTPException, Body, Cookie, Query, Path, UploadFile, File
from fastapi.responses import JSONResponse, Response
from fastapi.exceptions import RequestValidationError
from typing import Optional
from pydantic import ValidationError
from app.users.users_scheme import UpdateUserRequest, UpdatePasswordRequest
from app.users.users_controller import UsersController

router = APIRouter(prefix="/users", tags=["users"])

# 프로필이미지 업로드
@router.post("/{user_id}/profile-image", status_code=201)
async def upload_profile_image(
    user_id: int = Path(..., description="사용자 ID"),
    session_id: Optional[str] = Cookie(None),
    profileImage: Optional[UploadFile] = File(None, description="프로필 이미지 파일 (.jpg)")
):
    """프로필 이미지 업로드 API"""
    try:
        # Controller 호출
        return await UsersController.upload_profile_image(
            user_id=user_id,
            session_id=session_id,
            profile_image=profileImage
        )
    except HTTPException as e:
        # status code: Controller에서 발생한 에러 코드 (400, 401, 403, 404 등)
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

# 이메일 중복 체크 (구체적 경로이므로 경로 파라미터보다 먼저 정의)
@router.get("/check-email", status_code=200)
async def check_email(email: Optional[str] = Query(None, description="이메일")):
    """이메일 중복 체크 API"""
    try:
        # Controller 호출
        return UsersController.check_email(email=email)
    except HTTPException as e:
        # status code: Controller에서 발생한 에러 코드 (400 등)
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

# 닉네임 중복 체크 (구체적 경로이므로 경로 파라미터보다 먼저 정의)
@router.get("/check-nickname", status_code=200)
async def check_nickname(nickname: Optional[str] = Query(None, description="닉네임")):
    """닉네임 중복 체크 API"""
    try:
        # Controller 호출
        return UsersController.check_nickname(nickname=nickname)
    except HTTPException as e:
        # status code: Controller에서 발생한 에러 코드 (400, 409 등)
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

# 내 정보 조회
@router.get("/{user_id}", status_code=200)
async def get_user(user_id: int = Path(..., description="사용자 ID"), session_id: Optional[str] = Cookie(None)):
    """내 정보 조회 API"""
    try:
        # Controller 호출
        return UsersController.get_user(user_id=user_id, session_id=session_id)
    except HTTPException as e:
        # status code: Controller에서 발생한 에러 코드 (400, 401, 403, 404 등)
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

# 내 정보 수정
@router.patch("/{user_id}", status_code=200)
async def update_user(user_id: int = Path(..., description="사용자 ID"), session_id: Optional[str] = Cookie(None), user_data: Optional[UpdateUserRequest] = Body(None)):
    """내 정보 수정 API"""
    try:
        # status code 400번
        # 빈 body 체크
        if user_data is None:
            return JSONResponse(
                status_code=400,
                content={"code": "INVALID_REQUEST_BODY", "data": None}
            )
        
        # Controller 호출
        return UsersController.update_user(
            user_id=user_id,
            session_id=session_id,
            nickname=user_data.nickname,
            profile_image_url=user_data.profileImageUrl
        )
    except HTTPException as e:
        # status code: Controller에서 발생한 에러 코드 (400, 401, 403, 404, 409 등)
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
            
            if "nickname" in str(field).lower():
                return JSONResponse(
                    status_code=400,
                    content={"code": "INVALID_NICKNAME_FORMAT", "data": None}
                )
            elif "profileimageurl" in str(field).lower():
                return JSONResponse(
                    status_code=400,
                    content={"code": "INVALID_PROFILEIMAGEURL", "data": None}
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

# 비밀번호 변경
@router.patch("/{user_id}/password", status_code=200)
async def update_password(user_id: int = Path(..., description="사용자 ID"), session_id: Optional[str] = Cookie(None), password_data: Optional[UpdatePasswordRequest] = Body(None)):
    """비밀번호 변경 API"""
    try:
        # status code 400번
        # 빈 body 체크
        if password_data is None:
            return JSONResponse(
                status_code=400,
                content={"code": "INVALID_REQUEST_BODY", "data": None}
            )
        
        # Controller 호출
        return UsersController.update_password(
            user_id=user_id,
            session_id=session_id,
            current_password=password_data.currentPassword,
            new_password=password_data.newPassword
        )
    except HTTPException as e:
        # status code: Controller에서 발생한 에러 코드 (400, 401, 403, 404 등)
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
            
            if "currentpassword" in str(field).lower() or "newpassword" in str(field).lower():
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

# 회원 탈퇴
@router.delete("/{user_id}", status_code=204)
async def withdraw_user(user_id: int = Path(..., description="사용자 ID"), session_id: Optional[str] = Cookie(None)):
    """회원 탈퇴 API"""
    try:
        # Controller 호출
        UsersController.withdraw_user(user_id=user_id, session_id=session_id)
        
        # status code 204번(탈퇴 성공) - 응답 본문 없음
        return Response(status_code=204)
    except HTTPException as e:
        # status code: Controller에서 발생한 에러 코드 (400, 401, 403, 404 등)
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
