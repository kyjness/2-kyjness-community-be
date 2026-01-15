# app/routes/posts_route.py
from fastapi import APIRouter, HTTPException, Body, Cookie, Query, Path, UploadFile, File
from fastapi.responses import JSONResponse, Response
from fastapi.exceptions import RequestValidationError
from typing import Optional
from pydantic import ValidationError
from app.posts.posts_scheme import PostCreateRequest, PostUpdateRequest
from app.posts.posts_controller import PostsController
from app.models.auth_model import AuthModel

router = APIRouter(prefix="/posts", tags=["posts"])

# 게시글 작성
@router.post("", status_code=201)
async def create_post(
    session_id: Optional[str] = Cookie(None),
    post_data: Optional[PostCreateRequest] = Body(None)
):
    """게시글 작성 API"""
    try:
        # status code 401번
        # 인증 정보 없음
        if not session_id:
            return JSONResponse(
                status_code=401,
                content={"code": "UNAUTHORIZED", "data": None}
            )
        
        # 세션 ID 검증
        user_id = AuthModel.verify_token(session_id)
        if not user_id:
            return JSONResponse(
                status_code=401,
                content={"code": "UNAUTHORIZED", "data": None}
            )
        
        # status code 400번
        # 빈 body 체크
        if post_data is None:
            return JSONResponse(
                status_code=400,
                content={"code": "INVALID_REQUEST_BODY", "data": None}
            )
        
        # Controller 호출
        return PostsController.create_post(
            user_id=user_id,
            title=post_data.title,
            content=post_data.content,
            file_url=post_data.fileUrl or ""
        )
    except HTTPException as e:
        # status code: Controller에서 발생한 에러 코드 (400 등)
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
            
            if "title" in str(field).lower():
                return JSONResponse(
                    status_code=400,
                    content={"code": "INVALID_TITLE_FORMAT", "data": None}
                )
            elif "content" in str(field).lower():
                return JSONResponse(
                    status_code=400,
                    content={"code": "INVALID_CONTENT_FORMAT", "data": None}
                )
            elif "fileurl" in str(field).lower():
                return JSONResponse(
                    status_code=400,
                    content={"code": "INVALID_FILEURL", "data": None}
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

# 게시글 이미지 업로드
@router.post("/{post_id}/image", status_code=201)
async def upload_post_image(
    post_id: int = Path(..., description="게시글 ID"),
    session_id: Optional[str] = Cookie(None),
    postFile: Optional[UploadFile] = File(None, description="게시글 이미지 파일")
):
    """게시글 이미지 업로드 API"""
    try:
        # status code 401번
        # 인증 정보 없음
        if not session_id:
            return JSONResponse(
                status_code=401,
                content={"code": "UNAUTHORIZED", "data": None}
            )
        
        # 세션 ID 검증
        user_id = AuthModel.verify_token(session_id)
        if not user_id:
            return JSONResponse(
                status_code=401,
                content={"code": "UNAUTHORIZED", "data": None}
            )
        
        # status code 400번
        # 파일 없음
        if not postFile:
            return JSONResponse(
                status_code=400,
                content={"code": "MISSING_REQUIRED_FIELD", "data": None}
            )
        
        # Controller 호출
        return await PostsController.upload_post_image(
            post_id=post_id,
            session_id=session_id,
            file=postFile
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

# 게시글 목록 조회
@router.get("", status_code=200)
async def get_posts(
    page: int = Query(1, ge=1, description="페이지 번호"),
    size: int = Query(10, ge=1, description="페이지 크기 (기본값: 10)")
):
    """게시글 목록 조회 API"""
    try:
        # Controller 호출
        return PostsController.get_posts(page=page, size=size)
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

# 게시글 상세 조회
@router.get("/{post_id}", status_code=200)
async def get_post(post_id: int = Path(..., description="게시글 ID")):
    """게시글 상세 조회 API"""
    try:
        # Controller 호출
        return PostsController.get_post(post_id=post_id)
    except HTTPException as e:
        # status code: Controller에서 발생한 에러 코드 (400, 404 등)
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

# 게시글 수정
@router.patch("/{post_id}", status_code=200)
async def update_post(
    post_id: int = Path(..., description="게시글 ID"),
    session_id: Optional[str] = Cookie(None),
    post_data: Optional[PostUpdateRequest] = Body(None)
):
    """게시글 수정 API"""
    try:
        # status code 401번
        # 인증 정보 없음
        if not session_id:
            return JSONResponse(
                status_code=401,
                content={"code": "UNAUTHORIZED", "data": None}
            )
        
        # 세션 ID 검증
        user_id = AuthModel.verify_token(session_id)
        if not user_id:
            return JSONResponse(
                status_code=401,
                content={"code": "UNAUTHORIZED", "data": None}
            )
        
        # status code 400번
        # 빈 body 체크
        if post_data is None:
            return JSONResponse(
                status_code=400,
                content={"code": "INVALID_REQUEST_BODY", "data": None}
            )
        
        # Controller 호출
        return PostsController.update_post(
            user_id=user_id,
            post_id=post_id,
            session_id=session_id,
            title=post_data.title,
            content=post_data.content,
            file_url=post_data.fileUrl
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
            
            if "title" in str(field).lower():
                return JSONResponse(
                    status_code=400,
                    content={"code": "INVALID_TITLE_FORMAT", "data": None}
                )
            elif "content" in str(field).lower():
                return JSONResponse(
                    status_code=400,
                    content={"code": "INVALID_CONTENT_FORMAT", "data": None}
                )
            elif "fileurl" in str(field).lower():
                return JSONResponse(
                    status_code=400,
                    content={"code": "INVALID_FILEURL", "data": None}
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

# 게시글 삭제
@router.delete("/{post_id}", status_code=204)
async def delete_post(
    post_id: int = Path(..., description="게시글 ID"),
    session_id: Optional[str] = Cookie(None)
):
    """게시글 삭제 API"""
    try:
        # status code 401번
        # 인증 정보 없음
        if not session_id:
            return JSONResponse(
                status_code=401,
                content={"code": "UNAUTHORIZED", "data": None}
            )
        
        # 세션 ID 검증
        user_id = AuthModel.verify_token(session_id)
        if not user_id:
            return JSONResponse(
                status_code=401,
                content={"code": "UNAUTHORIZED", "data": None}
            )
        
        # Controller 호출
        PostsController.delete_post(user_id=user_id, post_id=post_id, session_id=session_id)
        
        # status code 204번(삭제 성공) - 응답 본문 없음
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
