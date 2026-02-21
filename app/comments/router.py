# app/comments/router.py
"""댓글 라우트."""

from fastapi import APIRouter, Depends, Path, Query
from fastapi.responses import Response

from app.comments.schema import CommentCreateRequest, CommentUpdateRequest
from app.comments import controller
from app.core.dependencies import get_current_user, require_comment_author
from app.core.response import ApiResponse

router = APIRouter(prefix="/posts/{post_id}/comments", tags=["comments"])


@router.post("", status_code=201, response_model=ApiResponse)
async def create_comment(
    comment_data: CommentCreateRequest,
    post_id: int = Path(..., description="게시글 ID"),
    user_id: int = Depends(get_current_user),
):
    """댓글 작성."""
    return controller.create_comment(post_id=post_id, user_id=user_id, data=comment_data)


@router.get("", status_code=200, response_model=ApiResponse)
async def get_comments(
    post_id: int = Path(..., description="게시글 ID"),
    page: int = Query(1, ge=1, description="페이지 번호"),
    size: int = Query(10, ge=1, le=100, description="페이지 크기"),
):
    """댓글 목록 조회."""
    return controller.get_comments(post_id=post_id, page=page, size=size)


@router.patch("/{comment_id}", status_code=200, response_model=ApiResponse)
async def update_comment(
    comment_data: CommentUpdateRequest,
    post_id: int = Path(..., description="게시글 ID"),
    comment_id: int = Path(..., description="댓글 ID"),
    user_id: int = Depends(get_current_user),
    _: int = Depends(require_comment_author),
):
    """댓글 수정."""
    return controller.update_comment(
        post_id=post_id, comment_id=comment_id, user_id=user_id, data=comment_data
    )


@router.delete("/{comment_id}", status_code=204)
async def withdraw_comment(
    post_id: int = Path(..., description="게시글 ID"),
    comment_id: int = Path(..., description="댓글 ID"),
    user_id: int = Depends(get_current_user),
    _: int = Depends(require_comment_author),
):
    """댓글 철회 (deleted_at 저장)."""
    controller.withdraw_comment(post_id=post_id, comment_id=comment_id, user_id=user_id)
    return Response(status_code=204)
