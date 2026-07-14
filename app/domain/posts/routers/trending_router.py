from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import CurrentUser, get_current_user_optional, get_slave_db
from app.common import ApiCode, ApiResponse, api_response
from app.domain.posts.schemas import TrendingPostResponse
from app.domain.posts.services import TrendingPostService
from app.infra.redis import get_app_redis

router = APIRouter(prefix="/posts", tags=["posts"])


@router.get(
    "/trending",
    status_code=200,
    response_model=ApiResponse[list[TrendingPostResponse]],
)
async def get_trending_posts(
    request: Request,
    limit: int = Query(10, ge=1, le=10, description="인기글 최대 개수 (최대 10)"),
    category_id: int | None = Query(None, ge=1, description="카테고리 ID 필터"),
    db: AsyncSession = Depends(get_slave_db),
    current_user: CurrentUser | None = Depends(get_current_user_optional),
):
    # 집계 창은 서버 고정 24h(서비스 상수) — 클라이언트 제어(1~48h)는 소비자 없이
    # 캐시 키만 값별로 분화시키는 표면이라 제거했다(ADR 0004).
    redis = get_app_redis(request.app)
    result = await TrendingPostService.get_trending_posts(
        db=db,
        redis_client=redis,
        limit=limit,
        category_id=category_id,
        current_user_id=current_user.id if current_user else None,
    )
    return api_response(request, code=ApiCode.OK, data=result)
