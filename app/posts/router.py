# app/posts/router.py

from fastapi import APIRouter, Depends, Path, Query
from fastapi.responses import Response
from starlette.responses import JSONResponse

from app.posts.schema import PostCreateRequest, PostUpdateRequest
from app.posts import controller
from app.core.dependencies import get_current_user, require_post_author
from app.core.response import ApiResponse

router = APIRouter(prefix="/posts", tags=["posts"])


@router.post("", status_code=201, response_model=ApiResponse)
async def create_post(post_data: PostCreateRequest, user_id: int = Depends(get_current_user)):
    return controller.create_post(user_id=user_id, data=post_data)


@router.get("", status_code=200, response_model=ApiResponse)
async def get_posts(page: int = Query(1, ge=1, description="페이지 번호"), size: int = Query(10, ge=1, le=100, description="페이지 크기 (기본 10, 최대 100)")):
    return controller.get_posts(page=page, size=size)


@router.post("/{post_id}/view", status_code=204)
async def record_view(post_id: int = Path(..., description="게시글 ID")):
    controller.record_post_view(post_id)
    return Response(status_code=204)


@router.get("/{post_id}", status_code=200, response_model=ApiResponse)
async def get_post(post_id: int = Path(..., description="게시글 ID")):
    return controller.get_post(post_id=post_id)


@router.patch("/{post_id}", status_code=200, response_model=ApiResponse)
async def update_post(post_data: PostUpdateRequest, post_id: int = Path(..., description="게시글 ID"), _: int = Depends(require_post_author)):
    return controller.update_post(post_id=post_id, data=post_data)


@router.delete("/{post_id}", status_code=204)
async def withdraw_post(post_id: int = Path(..., description="게시글 ID"), _: int = Depends(require_post_author)):
    controller.withdraw_post(post_id=post_id)
    return Response(status_code=204)


@router.post("/{post_id}/likes")
async def like(post_id: int = Path(..., description="게시글 ID"), user_id: int = Depends(get_current_user)):
    result, status_code = controller.create_like(post_id=post_id, user_id=user_id)
    return JSONResponse(content=result, status_code=status_code)


@router.delete("/{post_id}/likes", status_code=200)
async def unlike(post_id: int = Path(..., description="게시글 ID"), user_id: int = Depends(get_current_user)):
    return controller.delete_like(post_id=post_id, user_id=user_id)
