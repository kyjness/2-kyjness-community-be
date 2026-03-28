# Likes 라우터. Router → Service. 예외는 전역 handler 처리.
from fastapi import APIRouter, Depends, Path, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import CurrentUser, get_current_user, get_master_db
from app.common import ApiCode, ApiResponse, api_response
from app.likes.schema import LikeResponseData
from app.likes.service import LikeService

router = APIRouter(prefix="/likes", tags=["likes"])


@router.post("/posts/{post_id}", status_code=200, response_model=ApiResponse[LikeResponseData])
async def like_post(
    request: Request,
    post_id: str = Path(..., min_length=26, max_length=26, description="게시글 ULID"),
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_master_db),
):
    is_liked, like_count, inserted = await LikeService.like_post(post_id, user.id, db=db)
    code = ApiCode.LIKE_SUCCESS if inserted else ApiCode.ALREADY_LIKED
    return api_response(
        request, code=code, data=LikeResponseData(is_liked=is_liked, like_count=like_count)
    )


@router.delete("/posts/{post_id}", status_code=200, response_model=ApiResponse[LikeResponseData])
async def unlike_post(
    request: Request,
    post_id: str = Path(..., min_length=26, max_length=26, description="게시글 ULID"),
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_master_db),
):
    is_liked, like_count = await LikeService.unlike_post(post_id, user.id, db=db)
    return api_response(
        request,
        code=ApiCode.LIKE_DELETED,
        data=LikeResponseData(is_liked=is_liked, like_count=like_count),
    )


@router.post(
    "/comments/{comment_id}",
    status_code=200,
    response_model=ApiResponse[LikeResponseData],
)
async def like_comment(
    request: Request,
    comment_id: str = Path(..., min_length=26, max_length=26, description="댓글 ULID"),
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_master_db),
):
    is_liked, like_count, inserted = await LikeService.like_comment(comment_id, user.id, db=db)
    code = ApiCode.LIKE_SUCCESS if inserted else ApiCode.ALREADY_LIKED
    return api_response(
        request, code=code, data=LikeResponseData(is_liked=is_liked, like_count=like_count)
    )


@router.delete(
    "/comments/{comment_id}",
    status_code=200,
    response_model=ApiResponse[LikeResponseData],
)
async def unlike_comment(
    request: Request,
    comment_id: str = Path(..., min_length=26, max_length=26, description="댓글 ULID"),
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_master_db),
):
    is_liked, like_count = await LikeService.unlike_comment(comment_id, user.id, db=db)
    return api_response(
        request,
        code=ApiCode.LIKE_DELETED,
        data=LikeResponseData(is_liked=is_liked, like_count=like_count),
    )
