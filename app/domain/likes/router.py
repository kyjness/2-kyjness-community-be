# Likes 라우터. Router → Service. 예외는 전역 handler 처리.
from fastapi import APIRouter, Depends, Path
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import CurrentUser, get_current_user, get_master_db
from app.common import ApiCode, ApiResponse
from app.domain.likes.schema import LikeResponseData
from app.domain.likes.service import LikeService

router = APIRouter(prefix="/likes", tags=["likes"])


@router.post(
    "/posts/{post_id}", status_code=200, response_model=ApiResponse[LikeResponseData]
)
async def like_post(
    post_id: int = Path(..., ge=1, description="게시글 ID"),
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_master_db),
):
    is_liked, like_count, inserted = await LikeService.like_post(
        post_id, user.id, db=db
    )
    code = ApiCode.LIKE_SUCCESS.value if inserted else ApiCode.ALREADY_LIKED.value
    return ApiResponse(
        code=code, data=LikeResponseData(is_liked=is_liked, like_count=like_count)
    )


@router.delete(
    "/posts/{post_id}", status_code=200, response_model=ApiResponse[LikeResponseData]
)
async def unlike_post(
    post_id: int = Path(..., ge=1, description="게시글 ID"),
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_master_db),
):
    is_liked, like_count = await LikeService.unlike_post(post_id, user.id, db=db)
    return ApiResponse(
        code=ApiCode.LIKE_DELETED.value,
        data=LikeResponseData(is_liked=is_liked, like_count=like_count),
    )


@router.post(
    "/comments/{comment_id}",
    status_code=200,
    response_model=ApiResponse[LikeResponseData],
)
async def like_comment(
    comment_id: int = Path(..., ge=1, description="댓글 ID"),
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_master_db),
):
    is_liked, like_count, inserted = await LikeService.like_comment(
        comment_id, user.id, db=db
    )
    code = ApiCode.LIKE_SUCCESS.value if inserted else ApiCode.ALREADY_LIKED.value
    return ApiResponse(
        code=code, data=LikeResponseData(is_liked=is_liked, like_count=like_count)
    )


@router.delete(
    "/comments/{comment_id}",
    status_code=200,
    response_model=ApiResponse[LikeResponseData],
)
async def unlike_comment(
    comment_id: int = Path(..., ge=1, description="댓글 ID"),
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_master_db),
):
    is_liked, like_count = await LikeService.unlike_comment(comment_id, user.id, db=db)
    return ApiResponse(
        code=ApiCode.LIKE_DELETED.value,
        data=LikeResponseData(is_liked=is_liked, like_count=like_count),
    )
