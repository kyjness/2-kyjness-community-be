# app/api/v1.py
"""v1 API 라우터 조립."""

from fastapi import APIRouter

from app.auth.auth_route import router as auth_router
from app.users.users_route import router as users_router
from app.posts.posts_route import router as posts_router
from app.comments.comments_route import router as comments_router
from app.media.media_route import router as media_router


v1_router = APIRouter(prefix="/v1", tags=["v1"])
v1_router.include_router(auth_router)
v1_router.include_router(users_router)
v1_router.include_router(media_router)
v1_router.include_router(posts_router)
v1_router.include_router(comments_router)
