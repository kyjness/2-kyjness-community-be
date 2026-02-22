# app/comments/router.py

from fastapi import APIRouter, Depends, Path, Query
from fastapi.responses import Response

from app.comments.schema import CommentUpsertRequest
from app.comments import controller
from app.core.dependencies import get_current_user, require_comment_author, CommentAuthorContext
from app.core.response import ApiResponse

router = APIRouter(prefix="/posts/{post_id}/comments", tags=["comments"])


@router.post("", status_code=201, response_model=ApiResponse)
async def create_comment(comment_data: CommentUpsertRequest, post_id: int = Path(..., description="게시글 ID"), user_id: int = Depends(get_current_user)):
    return controller.create_comment(post_id=post_id, user_id=user_id, data=comment_data)

@router.get("", status_code=200, response_model=ApiResponse)
async def get_comments(post_id: int = Path(..., description="게시글 ID"), page: int = Query(1, ge=1, description="페이지 번호"), size: int = Query(10, ge=1, le=100, description="페이지 크기")):
    return controller.get_comments(post_id=post_id, page=page, size=size)

@router.patch("/{comment_id}", status_code=200, response_model=ApiResponse)
async def update_comment(comment_data: CommentUpsertRequest, post_id: int = Path(..., description="게시글 ID"), author_ctx: CommentAuthorContext = Depends(require_comment_author)):
    return controller.update_comment(post_id=post_id, comment_id=author_ctx.comment_id, data=comment_data)

@router.delete("/{comment_id}", status_code=204)
async def withdraw_comment(post_id: int = Path(..., description="게시글 ID"), author_ctx: CommentAuthorContext = Depends(require_comment_author)):
    controller.withdraw_comment(post_id=post_id, comment_id=author_ctx.comment_id)
    return Response(status_code=204)
