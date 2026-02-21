# app/api/v1.py
"""v1 API 라우터 조립."""

from fastapi import APIRouter

from app.auth.router import router as auth_router
from app.users.router import router as users_router
from app.posts.router import router as posts_router
from app.comments.router import router as comments_router
from app.media.router import router as media_router


# 라우터 조합 레이어. /v1 prefix만 부여. 각 도메인 router는 자체 prefix/tags 가짐.
v1_router = APIRouter(prefix="/v1")
v1_router.include_router(auth_router)
v1_router.include_router(users_router)
v1_router.include_router(media_router)
v1_router.include_router(posts_router)
v1_router.include_router(comments_router)
