# app/posts/posts_route.py
from fastapi import APIRouter, Query, UploadFile, File, Depends, Path
from fastapi.responses import Response
from typing import Optional
from app.posts.posts_schema import PostCreateRequest, PostUpdateRequest
from app.posts import posts_controller
from app.core.dependencies import get_current_user, require_post_author
from app.core.response import ApiResponse

router = APIRouter(prefix="/posts", tags=["posts"])

# 게시글 작성
@router.post("", status_code=201, response_model=ApiResponse)
async def create_post(
    post_data: PostCreateRequest,
    user_id: int = Depends(get_current_user)
):
    """게시글 작성 API"""
    return posts_controller.create_post(
        user_id=user_id,
        title=post_data.title,
        content=post_data.content,
        file_url=post_data.fileUrl or ""
    )

# 게시글 이미지 업로드
@router.post("/{post_id}/image", status_code=201, response_model=ApiResponse)
async def upload_post_image(
    post_id: int = Path(..., description="게시글 ID"),
    postFile: Optional[UploadFile] = File(None, description="게시글 이미지 파일"),
    user_id: int = Depends(get_current_user),
    _: int = Depends(require_post_author),
):
    """게시글 이미지 업로드 API"""
    return await posts_controller.upload_post_image(
        post_id=post_id,
        user_id=user_id,
        file=postFile
    )

# 게시글 목록 조회
@router.get("", status_code=200, response_model=ApiResponse)
async def get_posts(
    page: int = Query(1, ge=1, description="페이지 번호"),
    size: int = Query(10, ge=1, le=100, description="페이지 크기 (기본 10, 최대 100)")
):
    """게시글 목록 조회 API"""
    return posts_controller.get_posts(page=page, size=size)

# 게시글 상세 조회
@router.get("/{post_id}", status_code=200, response_model=ApiResponse)
async def get_post(post_id: int = Path(..., description="게시글 ID")):
    """게시글 상세 조회 API"""
    return posts_controller.get_post(post_id=post_id)

# 게시글 수정
@router.patch("/{post_id}", status_code=200, response_model=ApiResponse)
async def update_post(
    post_data: PostUpdateRequest,
    post_id: int = Path(..., description="게시글 ID"),
    user_id: int = Depends(get_current_user),
    _: int = Depends(require_post_author),
):
    """게시글 수정 API"""
    return posts_controller.update_post(
        post_id=post_id,
        user_id=user_id,
        title=post_data.title,
        content=post_data.content,
        file_url=post_data.fileUrl
    )

# 게시글 삭제
@router.delete("/{post_id}", status_code=204)
async def delete_post(
    post_id: int = Path(..., description="게시글 ID"),
    user_id: int = Depends(get_current_user),
    _: int = Depends(require_post_author),
):
    """게시글 삭제 API"""
    posts_controller.delete_post(post_id=post_id, user_id=user_id)
    return Response(status_code=204)


# 좋아요 추가
@router.post("/{post_id}/likes", status_code=201, response_model=ApiResponse)
async def create_like(
    post_id: int = Path(..., description="게시글 ID"),
    user_id: int = Depends(get_current_user),
):
    """게시글 좋아요 추가 API"""
    return posts_controller.create_like(post_id=post_id, user_id=user_id)


# 좋아요 취소
@router.delete("/{post_id}/likes", status_code=200, response_model=ApiResponse)
async def delete_like(
    post_id: int = Path(..., description="게시글 ID"),
    user_id: int = Depends(get_current_user),
):
    """게시글 좋아요 취소 API. 응답에 likeCount 포함."""
    return posts_controller.delete_like(post_id=post_id, user_id=user_id)
