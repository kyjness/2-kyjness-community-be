# app/posts/router.py
"""게시글 라우트."""

from fastapi import APIRouter, Depends, Path, Query
from fastapi.responses import Response
from starlette.responses import JSONResponse

from app.posts.schema import PostCreateRequest, PostUpdateRequest
from app.posts import controller
from app.core.dependencies import get_current_user, require_post_author
from app.core.response import ApiResponse

router = APIRouter(prefix="/posts", tags=["posts"])


@router.post("", status_code=201, response_model=ApiResponse)
async def create_post(
    post_data: PostCreateRequest,
    user_id: int = Depends(get_current_user),
):
    """게시글 작성. 이미지는 POST /v1/media/images 로 업로드 후 imageIds 전달 (최대 5개)."""
    return controller.create_post(user_id=user_id, data=post_data)


@router.get("", status_code=200, response_model=ApiResponse)
async def get_posts(
    page: int = Query(1, ge=1, description="페이지 번호"),
    size: int = Query(10, ge=1, le=100, description="페이지 크기 (기본 10, 최대 100)"),
):
    """게시글 목록 조회 (무한 스크롤, hasMore)."""
    return controller.get_posts(page=page, size=size)


@router.post("/{post_id}/view", status_code=204)
async def record_post_view(post_id: int = Path(..., description="게시글 ID")):
    """조회수 1 증가. 페이지 진입 시에만 호출."""
    controller.record_view(post_id)
    return Response(status_code=204)


@router.get("/{post_id}", status_code=200, response_model=ApiResponse)
async def get_post(post_id: int = Path(..., description="게시글 ID")):
    """게시글 상세 조회."""
    return controller.get_post(post_id=post_id)


@router.patch("/{post_id}", status_code=200, response_model=ApiResponse)
async def update_post(
    post_data: PostUpdateRequest,
    post_id: int = Path(..., description="게시글 ID"),
    user_id: int = Depends(get_current_user),
    _: int = Depends(require_post_author),
):
    """게시글 수정."""
    return controller.update_post(post_id=post_id, user_id=user_id, data=post_data)


@router.delete("/{post_id}", status_code=204)
async def withdraw_post(
    post_id: int = Path(..., description="게시글 ID"),
    user_id: int = Depends(get_current_user),
    _: int = Depends(require_post_author),
):
    """게시글 철회 (deleted_at 저장)."""
    controller.withdraw_post(post_id=post_id, user_id=user_id)
    return Response(status_code=204)


@router.post("/{post_id}/likes", status_code=201)
async def create_like(
    post_id: int = Path(..., description="게시글 ID"),
    user_id: int = Depends(get_current_user),
):
    """좋아요 추가."""
    result = controller.create_like(post_id=post_id, user_id=user_id)
    if result.get("code") == "ALREADY_LIKED":
        return JSONResponse(content=result, status_code=200)
    return result


@router.delete("/{post_id}/likes", status_code=200)
async def delete_like(
    post_id: int = Path(..., description="게시글 ID"),
    user_id: int = Depends(get_current_user),
):
    """좋아요 취소."""
    return controller.delete_like(post_id=post_id, user_id=user_id)
