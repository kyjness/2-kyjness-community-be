# 게시글 라우터. CRUD, 피드(목록), 상세, 좋아요, 조회수, 댓글 목록.
from fastapi import APIRouter, Depends, Path, Query
from sqlalchemy.orm import Session
from fastapi import Request
from fastapi.responses import Response

from app.common import ApiResponse
from app.common.schema import PaginatedResponse
from app.posts.schema import PostCreateRequest, PostIdData, PostResponse, PostUpdateRequest, LikeCountData
from app.posts import controller
from app.posts.view_cache import get_client_identifier
from app.api.dependencies import (
    CurrentUser,
    get_current_user,
    get_master_db,
    get_slave_db,
    require_post_author,
)

router = APIRouter(prefix="/posts", tags=["posts"])


@router.post("", status_code=201, response_model=ApiResponse[PostIdData])
def create_post(
    post_data: PostCreateRequest,
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_master_db),
):
    return controller.create_post(user=user, data=post_data, db=db)


@router.get("", status_code=200, response_model=ApiResponse[PaginatedResponse[PostResponse]])
def get_posts(
    page: int = Query(1, ge=1, description="페이지 번호"),
    size: int = Query(10, ge=1, le=100, description="페이지 크기"),
    db: Session = Depends(get_slave_db),
):
    return controller.get_posts(page=page, size=size, db=db)


@router.post("/{post_id}/view", status_code=204)
def record_view(
    request: Request,
    post_id: int = Path(..., ge=1, description="게시글 ID"),
    db: Session = Depends(get_master_db),
):
    client_id = get_client_identifier(request)
    controller.record_post_view(post_id, client_id, db=db)
    return Response(status_code=204)


@router.get("/{post_id}", status_code=200, response_model=ApiResponse[PostResponse])
def get_post(
    post_id: int = Path(..., ge=1, description="게시글 ID"),
    db: Session = Depends(get_slave_db),
):
    return controller.get_post(post_id=post_id, db=db)


@router.patch("/{post_id}", status_code=200, response_model=ApiResponse[None])
def update_post(
    post_data: PostUpdateRequest,
    post_id: int = Path(..., ge=1, description="게시글 ID"),
    _: int = Depends(require_post_author),
    db: Session = Depends(get_master_db),
):
    return controller.update_post(post_id=post_id, data=post_data, db=db)


@router.delete("/{post_id}", status_code=204)
def delete_post(
    post_id: int = Path(..., ge=1, description="게시글 ID"),
    _: int = Depends(require_post_author),
    db: Session = Depends(get_master_db),
):
    controller.delete_post(post_id=post_id, db=db)
    return Response(status_code=204)


@router.post("/{post_id}/likes", status_code=201, response_model=ApiResponse[LikeCountData])
def add_like(
    post_id: int = Path(..., ge=1, description="게시글 ID"),
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_master_db),
):
    return controller.add_like(post_id=post_id, user=user, db=db)


@router.delete("/{post_id}/likes", status_code=204)
def delete_like(
    post_id: int = Path(..., ge=1, description="게시글 ID"),
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_master_db),
):
    controller.delete_like(post_id=post_id, user=user, db=db)
    return Response(status_code=204)
