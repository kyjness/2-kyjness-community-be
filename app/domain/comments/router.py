# 댓글 라우터. Router → Service. 예외는 전역 handler 처리.

from typing import Annotated

from fastapi import APIRouter, Depends, Path, Query, Request
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import (
    CommentAuthorContext,
    CurrentUser,
    get_current_user,
    get_current_user_optional,
    get_master_db,
    get_optional_redis,
    get_slave_db,
    require_comment_author,
    require_comment_author_for_delete,
)
from app.comments.schema import CommentIdData, CommentsPageData, CommentUpsertRequest
from app.comments.service import CommentService
from app.common import ApiCode, ApiResponse, PublicId, api_response

router = APIRouter(prefix="/posts/{post_id}/comments", tags=["comments"])


@router.post("", status_code=201, response_model=ApiResponse[CommentIdData])
async def create_comment(
    request: Request,
    comment_data: CommentUpsertRequest,
    post_id: Annotated[PublicId, Path(..., description="게시글 공개 ID (Base62)")],
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_master_db),
    redis: Redis | None = Depends(get_optional_redis),
):
    data = await CommentService.create_comment(post_id, user.id, comment_data, db=db, redis=redis)
    return api_response(request, code=ApiCode.OK, data=data)


@router.get("", status_code=200, response_model=ApiResponse[CommentsPageData])
async def get_comments(
    request: Request,
    post_id: Annotated[PublicId, Path(..., description="게시글 공개 ID (Base62)")],
    page: int = Query(1, ge=1, description="페이지 번호"),
    size: int = Query(10, ge=1, le=100, description="페이지 크기"),
    sort: str | None = Query(None, description="정렬: latest|oldest|popular"),
    db: AsyncSession = Depends(get_slave_db),
    current_user: CurrentUser | None = Depends(get_current_user_optional),
):
    data = await CommentService.get_comments(
        post_id,
        page,
        size,
        db=db,
        sort=sort,
        current_user_id=current_user.id if current_user else None,
    )
    return api_response(request, code=ApiCode.OK, data=data)


@router.patch("/{comment_id}", status_code=200, response_model=ApiResponse[None])
async def update_comment(
    request: Request,
    comment_data: CommentUpsertRequest,
    author_ctx: CommentAuthorContext = Depends(require_comment_author),
    db: AsyncSession = Depends(get_master_db),
):
    await CommentService.update_comment(
        author_ctx.post_id, author_ctx.comment_id, comment_data, db=db
    )
    return api_response(request, code=ApiCode.OK, data=None)


@router.delete("/{comment_id}", status_code=200, response_model=ApiResponse[None])
async def delete_comment(
    request: Request,
    author_ctx: CommentAuthorContext = Depends(require_comment_author_for_delete),
    db: AsyncSession = Depends(get_master_db),
):
    await CommentService.delete_comment(author_ctx.post_id, author_ctx.comment_id, db=db)
    return api_response(request, code=ApiCode.OK, data=None)
