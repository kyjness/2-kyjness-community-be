from typing import Annotated

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
from app.common import (
    ApiCode,
    ApiResponse,
    CursorPage,
    OptionalPublicId,
    PublicId,
    api_response,
)
from app.domain.posts.schemas import PostCreateRequest, PostIdData, PostResponse, PostUpdateRequest
from app.domain.posts.services import PostService
from app.infra.redis import get_app_redis

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
        out = api_response(request, code=ApiCode.OK, data=PostIdData(id=post_id))
        await post_create_idempotency_after_success(request, user.id, x_idempotency_key, out)
        return out
    except Exception:
        await post_create_idempotency_after_failure(request, user.id, x_idempotency_key)
        raise


@router.get("", status_code=200, response_model=ApiResponse[CursorPage[PostResponse]])
async def get_posts(
    request: Request,
    cursor: Annotated[
        OptionalPublicId,
        Query(
            description="무한 스크롤: 직전 응답의 마지막 게시글 id(공개 ID). 미지정 시 최신부터.",
        ),
    ] = None,
    size: int = Query(10, ge=1, le=100, description="페이지 크기"),
    q: str | None = Query(
        None,
        description="검색어 (제목·본문·해시태그, pg_trgm GIN. 공백=AND, #태그=정확 매칭, 토큰 3자+)",
    ),
    category_id: int | None = Query(None, ge=1, description="카테고리 ID 필터"),
    db: AsyncSession = Depends(get_slave_db),
    current_user: CurrentUser | None = Depends(get_current_user_optional),
):
    result, has_more = await PostService.get_posts(
        size=size,
        db=db,
        q=q,
        category_id=category_id,
        current_user_id=current_user.id if current_user else None,
        cursor=cursor,
    )
    return api_response(
        request,
        code=ApiCode.OK,
        data=CursorPage(items=result, has_more=has_more),
    )


@router.get("/{post_id}", status_code=200, response_model=ApiResponse[PostResponse])
async def get_post(
    request: Request,
    post_id: Annotated[PublicId, Path(..., description="게시글 공개 ID (Base62)")],
    client_id: str = Depends(get_client_identifier),
    db: AsyncSession = Depends(get_slave_db),
    writer_db: AsyncSession = Depends(get_master_db),
    current_user: CurrentUser | None = Depends(get_current_user_optional),
):
    viewer_key = f"u:{current_user.id}" if current_user else f"ip:{client_id}"
    redis = get_app_redis(request.app)
    data = await PostService.get_post_detail(
        post_id,
        db=db,
        current_user_id=current_user.id if current_user else None,
        viewer_key=viewer_key,
        redis_client=redis,
        writer_db=writer_db,
    )
    return api_response(request, code=ApiCode.OK, data=data)


@router.patch(
    "/{post_id}",
    status_code=200,
    response_model=ApiResponse[None],
    dependencies=[Depends(require_post_author)],
)
async def update_post(
    request: Request,
    post_data: PostUpdateRequest,
    post_id: Annotated[PublicId, Path(..., description="게시글 공개 ID (Base62)")],
    db: AsyncSession = Depends(get_master_db),
):
    await PostService.update_post(post_id, post_data, db=db)
    return api_response(request, code=ApiCode.OK, data=None)


@router.delete(
    "/{post_id}",
    status_code=200,
    response_model=ApiResponse[None],
    dependencies=[Depends(require_post_author)],
)
async def delete_post(
    request: Request,
    post_id: Annotated[PublicId, Path(..., description="게시글 공개 ID (Base62)")],
    db: AsyncSession = Depends(get_master_db),
):
    await PostService.delete_post(post_id, db=db)
    return api_response(request, code=ApiCode.OK, data=None)
