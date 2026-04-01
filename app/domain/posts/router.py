from fastapi import APIRouter

from app.posts.routers.hashtag_router import router as hashtag_router
from app.posts.routers.post_router import router as post_router

# 하위 라우터에 prefix="/posts"를 둠: 부모에만 prefix 두고 child path=""를 include하면
# FastAPI가 "Prefix and path cannot be both empty"로 기동 실패할 수 있음.
#
# 등록 순서: 정적 경로(/trending-hashtags)가 동적 경로(/{post_id})보다 먼저여야 함.
# post_router를 먼저 넣으면 "trending-hashtags"가 post_id로 매칭되어 422 → FE는 빈 목록 처리.
router = APIRouter(tags=["posts"])

router.include_router(hashtag_router)
router.include_router(post_router)
