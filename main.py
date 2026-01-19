# main.py
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.auth.auth_route import router as auth_router
from app.users.users_route import router as users_router
from app.posts.posts_route import router as posts_router
from app.comments.comments_route import router as comments_router
from app.likes.likes_route import router as likes_router
from app.core.config import settings
from app.core.logging_config import configure_logging
from app.core.exception_handlers import register_exception_handlers
from app.core.middleware import global_policy_middleware

configure_logging()

app = FastAPI(
    title="PuppyTalk API",
    description="커뮤니티 백엔드 API",
    version="1.0.0"
)

app.middleware("http")(global_policy_middleware)

# CORS 설정 (프론트엔드와 연결할 때 필요)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

register_exception_handlers(app)

# 라우터 등록
app.include_router(auth_router)
app.include_router(users_router)
app.include_router(posts_router)
app.include_router(comments_router)
app.include_router(likes_router)

# 루트 엔드포인트 (서버 작동 확인용)
@app.get("/")
def root():
    return {
        "message": "PuppyTalk API is running!",
        "version": "1.0.0",
        "docs": "/docs"
    }

# 헬스체크 엔드포인트 (서버 상태 확인용)
@app.get("/health")
def health_check():
    return {"status": "healthy"}

