# main.py
from contextlib import asynccontextmanager

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
from app.core.middleware import global_policy_middleware, security_headers_middleware, sql_logging_middleware

configure_logging()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """앱 시작 시 DB 연결 및 콘솔에 '데이터베이스 연결 성공' 표시."""
    from app.core.database import init_database, close_database
    init_database()
    yield
    close_database()


app = FastAPI(
    title="PuppyTalk API",
    description="커뮤니티 백엔드 API",
    version="1.0.0",
    lifespan=lifespan,
)

app.middleware("http")(sql_logging_middleware)
app.middleware("http")(global_policy_middleware)
app.middleware("http")(security_headers_middleware)

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

# 루트: API 정보 (문서 링크 등)
@app.get("/")
def root():
    return {
        "code": "OK",
        "data": {
            "message": "PuppyTalk API is running!",
            "version": "1.0.0",
            "docs": "/docs",
        },
    }

# 헬스체크: 상태 확인 전용 (200 + code/data 통일)
@app.get("/health")
def health_check():
    return {"code": "HEALTH_OK", "data": {"status": "healthy"}}

