from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import CurrentUser, get_current_user_optional, get_slave_db
from app.common import ApiCode, ApiResponse, api_response
from app.domain.posts.schemas import TrendingPostResponse
from app.domain.posts.services import TrendingPostService

router = APIRouter(prefix="/posts", tags=["posts"])


@router.get(
    "/trending",
    status_code=200,
    response_model=ApiResponse[list[TrendingPostResponse]],
)
async def get_trending_posts(
    request: Request,
    limit: int = Query(10, ge=1, le=10, description="인기글 최대 개수 (최대 10)"),
    window_hours: int = Query(
        24,
        ge=1,
        le=48,
        description="시간 감쇠 집계 창(시간). 인덱스 범위 스캔용 상한 48h.",
    ),
    category_id: int | None = Query(None, ge=1, description="카테고리 ID 필터"),
    db: AsyncSession = Depends(get_slave_db),
    current_user: CurrentUser | None = Depends(get_current_user_optional),
):
    redis = getattr(request.app.state, "redis", None)
    result = await TrendingPostService.get_trending_posts(
        db=db,
        redis_client=redis,
        limit=limit,
        window_hours=window_hours,
        category_id=category_id,
        current_user_id=current_user.id if current_user else None,
    )
    return api_response(request, code=ApiCode.OK, data=result)
