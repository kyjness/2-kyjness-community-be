from fastapi import APIRouter, Depends, Header, Path, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import (
    CurrentUser,
    get_client_identifier,
    get_current_user,
    get_current_user_optional,
    get_master_db,
    get_slave_db,
    post_create_idempotency_after_failure,
    post_create_idempotency_after_success,
    post_create_idempotency_before,
    require_post_author,
)
from app.common import ApiCode, ApiResponse, PaginatedResponse, api_response
from app.posts.schemas import PostCreateRequest, PostIdData, PostResponse, PostUpdateRequest
from app.posts.services import PostService

router = APIRouter(prefix="/posts", tags=["posts"])


@router.post("", status_code=201, response_model=ApiResponse[PostIdData])
async def create_post(
    request: Request,
    post_data: PostCreateRequest,
    x_idempotency_key: str | None = Header(default=None, alias="X-Idempotency-Key"),
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_master_db),
):
    cached = await post_create_idempotency_before(request, user.id, x_idempotency_key)
    if cached is not None:
        return cached
    try:
        post_id = await PostService.create_post(user.id, post_data, db=db)
        out = api_response(request, code=ApiCode.POST_UPLOADED, data=PostIdData(id=post_id))
        await post_create_idempotency_after_success(request, user.id, x_idempotency_key, out)
        return out
    except Exception:
        await post_create_idempotency_after_failure(request, user.id, x_idempotency_key)
        raise


@router.get("", status_code=200, response_model=ApiResponse[PaginatedResponse[PostResponse]])
async def get_posts(
    request: Request,
    page: int = Query(1, ge=1, description="페이지 번호"),
    size: int = Query(10, ge=1, le=100, description="페이지 크기"),
    q: str | None = Query(None, description="검색어 (title, content ILIKE)"),
    category_id: int | None = Query(None, ge=1, description="카테고리 ID 필터"),
    db: AsyncSession = Depends(get_slave_db),
    current_user: CurrentUser | None = Depends(get_current_user_optional),
):
    result, has_more, total = await PostService.get_posts(
        page=page,
        size=size,
        db=db,
        q=q,
        category_id=category_id,
        current_user_id=current_user.id if current_user else None,
    )
    return api_response(
        request,
        code=ApiCode.POSTS_RETRIEVED,
        data=PaginatedResponse(items=result, has_more=has_more, total=total),
    )


@router.post("/{post_id}/view", status_code=200, response_model=ApiResponse[None])
async def record_view(
    request: Request,
    post_id: str = Path(..., min_length=26, max_length=26, description="게시글 ULID"),
    client_id: str = Depends(get_client_identifier),
    db: AsyncSession = Depends(get_master_db),
    current_user: CurrentUser | None = Depends(get_current_user_optional),
):
    viewer_key = f"u:{current_user.id}" if current_user else f"ip:{client_id}"
    redis = getattr(request.app.state, "redis", None)
    await PostService.record_post_view(
        post_id,
        viewer_key,
        db=db,
        current_user_id=current_user.id if current_user else None,
        redis_client=redis,
    )
    return api_response(request, code=ApiCode.POST_VIEW_RECORDED, data=None)


@router.get("/{post_id}", status_code=200, response_model=ApiResponse[PostResponse])
async def get_post(
    request: Request,
    post_id: str = Path(..., min_length=26, max_length=26, description="게시글 ULID"),
    client_id: str = Depends(get_client_identifier),
    db: AsyncSession = Depends(get_slave_db),
    writer_db: AsyncSession = Depends(get_master_db),
    current_user: CurrentUser | None = Depends(get_current_user_optional),
):
    viewer_key = f"u:{current_user.id}" if current_user else f"ip:{client_id}"
    redis = getattr(request.app.state, "redis", None)
    data = await PostService.get_post_detail(
        post_id,
        db=db,
        current_user_id=current_user.id if current_user else None,
        viewer_key=viewer_key,
        redis_client=redis,
        writer_db=writer_db,
    )
    return api_response(request, code=ApiCode.POST_RETRIEVED, data=data)


@router.patch(
    "/{post_id}",
    status_code=200,
    response_model=ApiResponse[None],
    dependencies=[Depends(require_post_author)],
)
async def update_post(
    request: Request,
    post_data: PostUpdateRequest,
    post_id: str = Path(..., min_length=26, max_length=26, description="게시글 ULID"),
    db: AsyncSession = Depends(get_master_db),
):
    await PostService.update_post(post_id, post_data, db=db)
    return api_response(request, code=ApiCode.POST_UPDATED, data=None)


@router.delete(
    "/{post_id}",
    status_code=200,
    response_model=ApiResponse[None],
    dependencies=[Depends(require_post_author)],
)
async def delete_post(
    request: Request,
    post_id: str = Path(..., min_length=26, max_length=26, description="게시글 ULID"),
    db: AsyncSession = Depends(get_master_db),
):
    await PostService.delete_post(post_id, db=db)
    return api_response(request, code=ApiCode.POST_DELETED, data=None)

