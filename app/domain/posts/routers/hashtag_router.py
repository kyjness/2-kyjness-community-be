from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_slave_db
from app.common import ApiCode, ApiResponse, api_response
from app.domain.posts.schemas import TrendingHashtagResponse
from app.domain.posts.services import HashtagService
from app.infra.redis import get_app_redis

router = APIRouter(prefix="/posts", tags=["posts"])


@router.get(
    "/trending-hashtags",
    status_code=200,
    response_model=ApiResponse[list[TrendingHashtagResponse]],
)
async def get_trending_hashtags(
    request: Request,
    db: AsyncSession = Depends(get_slave_db),
):
    redis = get_app_redis(request.app)
    result = await HashtagService.get_trending_hashtags(db=db, redis_client=redis, limit=10)
    return api_response(request, code=ApiCode.OK, data=result)
