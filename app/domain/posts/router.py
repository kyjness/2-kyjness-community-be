# 게시글 라우터. Router → Service. 예외는 전역 handler 처리.

from fastapi import APIRouter, Depends, Path, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import (
    CurrentUser,
    get_client_identifier,
    get_current_user,
    get_current_user_optional,
    get_master_db,
    get_slave_db,
    require_post_author,
)
from app.common import ApiCode, ApiResponse, PaginatedResponse
from app.posts.schema import (
    PostCreateRequest,
    PostIdData,
    PostResponse,
    PostUpdateRequest,
)
from app.posts.service import PostService

router = APIRouter(prefix="/posts", tags=["posts"])


@router.post("", status_code=201, response_model=ApiResponse[PostIdData])
async def create_post(
    post_data: PostCreateRequest,
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_master_db),
):
    post_id = await PostService.create_post(user.id, post_data, db=db)
    return ApiResponse(code=ApiCode.POST_UPLOADED.value, data=PostIdData(id=post_id))


@router.get("", status_code=200, response_model=ApiResponse[PaginatedResponse[PostResponse]])
async def get_posts(
    page: int = Query(1, ge=1, description="페이지 번호"),
    size: int = Query(10, ge=1, le=100, description="페이지 크기"),
    q: str | None = Query(None, description="검색어 (title, content ILIKE)"),
    sort: str | None = Query(None, description="정렬: latest|popular|views|oldest"),
    db: AsyncSession = Depends(get_slave_db),
    current_user: CurrentUser | None = Depends(get_current_user_optional),
):
    result, has_more, total = await PostService.get_posts(
        page=page,
        size=size,
        db=db,
        q=q,
        sort=sort,
        current_user_id=current_user.id if current_user else None,
    )
    return ApiResponse(
        code=ApiCode.POSTS_RETRIEVED.value,
        data=PaginatedResponse(items=result, has_more=has_more, total=total),
    )


@router.post("/{post_id}/view", status_code=200, response_model=ApiResponse[None])
async def record_view(
    post_id: int = Path(..., ge=1, description="게시글 ID"),
    client_id: str = Depends(get_client_identifier),
    db: AsyncSession = Depends(get_master_db),
    current_user: CurrentUser | None = Depends(get_current_user_optional),
):
    await PostService.record_post_view(
        post_id,
        client_id,
        db=db,
        current_user_id=current_user.id if current_user else None,
    )
    return ApiResponse(code=ApiCode.POST_VIEW_RECORDED.value, data=None)


@router.get("/{post_id}", status_code=200, response_model=ApiResponse[PostResponse])
async def get_post(
    post_id: int = Path(..., ge=1, description="게시글 ID"),
    db: AsyncSession = Depends(get_slave_db),
    current_user: CurrentUser | None = Depends(get_current_user_optional),
):
    data = await PostService.get_post_detail(
        post_id, db=db, current_user_id=current_user.id if current_user else None
    )
    return ApiResponse(code=ApiCode.POST_RETRIEVED.value, data=data)


@router.patch(
    "/{post_id}",
    status_code=200,
    response_model=ApiResponse[None],
    dependencies=[Depends(require_post_author)],
)
async def update_post(
    post_data: PostUpdateRequest,
    post_id: int = Path(..., ge=1, description="게시글 ID"),
    db: AsyncSession = Depends(get_master_db),
):
    await PostService.update_post(post_id, post_data, db=db)
    return ApiResponse(code=ApiCode.POST_UPDATED.value, data=None)


@router.delete(
    "/{post_id}",
    status_code=200,
    response_model=ApiResponse[None],
    dependencies=[Depends(require_post_author)],
)
async def delete_post(
    post_id: int = Path(..., ge=1, description="게시글 ID"),
    db: AsyncSession = Depends(get_master_db),
):
    await PostService.delete_post(post_id, db=db)
    return ApiResponse(code=ApiCode.POST_DELETED.value, data=None)
