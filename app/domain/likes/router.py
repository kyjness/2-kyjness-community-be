# Likes 라우터. Router → Service. 예외는 전역 handler 처리.
from typing import Annotated

from fastapi import APIRouter, Depends, Path, Request
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import CurrentUser, get_current_user, get_master_db, get_optional_redis
from app.common import ApiCode, ApiResponse, PublicId, api_response
from app.likes.schema import LikeResponseData
from app.likes.service import LikeService

router = APIRouter(prefix="/likes", tags=["likes"])


@router.post("/posts/{post_id}", status_code=200, response_model=ApiResponse[LikeResponseData])
async def like_post(
    request: Request,
    post_id: Annotated[PublicId, Path(..., description="게시글 공개 ID (Base62)")],
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_master_db),
    redis: Redis | None = Depends(get_optional_redis),
):
    is_liked, like_count, inserted = await LikeService.like_post(
        post_id, user.id, db=db, redis=redis
    )
    code = ApiCode.OK if inserted else ApiCode.ALREADY_LIKED
    return api_response(
        request, code=code, data=LikeResponseData(is_liked=is_liked, like_count=like_count)
    )


@router.delete("/posts/{post_id}", status_code=200, response_model=ApiResponse[LikeResponseData])
async def unlike_post(
    request: Request,
    post_id: Annotated[PublicId, Path(..., description="게시글 공개 ID (Base62)")],
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_master_db),
):
    is_liked, like_count = await LikeService.unlike_post(post_id, user.id, db=db)
    return api_response(
        request,
        code=ApiCode.OK,
        data=LikeResponseData(is_liked=is_liked, like_count=like_count),
    )


@router.post(
    "/comments/{comment_id}",
    status_code=200,
    response_model=ApiResponse[LikeResponseData],
)
async def like_comment(
    request: Request,
    comment_id: Annotated[PublicId, Path(..., description="댓글 공개 ID (Base62)")],
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_master_db),
    redis: Redis | None = Depends(get_optional_redis),
):
    is_liked, like_count, inserted = await LikeService.like_comment(
        comment_id, user.id, db=db, redis=redis
    )
    code = ApiCode.OK if inserted else ApiCode.ALREADY_LIKED
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
    comment_id: Annotated[PublicId, Path(..., description="댓글 공개 ID (Base62)")],
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_master_db),
):
    is_liked, like_count = await LikeService.unlike_comment(comment_id, user.id, db=db)
    return api_response(
        request,
        code=ApiCode.OK,
        data=LikeResponseData(is_liked=is_liked, like_count=like_count),
    )
