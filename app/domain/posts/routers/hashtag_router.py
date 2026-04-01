from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_slave_db
from app.common import ApiCode, ApiResponse, api_response
from app.posts.schemas import TrendingHashtagResponse
from app.posts.services import HashtagService

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
    redis = getattr(request.app.state, "redis", None)
    result = await HashtagService.get_trending_hashtags(db=db, redis_client=redis, limit=10)
    return api_response(request, code=ApiCode.TRENDING_HASHTAGS_RETRIEVED, data=result)

