# /v1 prefix 라우터. auth, users, media, posts, comments, likes, dogs 라우터를 include.
from fastapi import APIRouter

from app.admin.router import router as admin_router
from app.auth.router import router as auth_router
from app.comments.router import router as comments_router
from app.dogs.router import router as dogs_router
from app.domain.likes.router import router as likes_router
from app.media.router import router as media_router
from app.posts.router import router as posts_router
from app.reports.router import router as reports_router
from app.users.router import router as users_router

v1_router = APIRouter(prefix="/v1", strict_slashes=False)
v1_router.include_router(auth_router)
v1_router.include_router(users_router)
v1_router.include_router(dogs_router)
v1_router.include_router(media_router)
v1_router.include_router(posts_router)
v1_router.include_router(comments_router)
v1_router.include_router(likes_router)
v1_router.include_router(reports_router)
v1_router.include_router(admin_router)
