# main.py
import logging
from pathlib import Path

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from starlette.requests import Request

from app.auth.auth_route import router as auth_router
from app.users.users_route import router as users_router
from app.posts.posts_route import router as posts_router
from app.comments.comments_route import router as comments_router
from app.likes.likes_route import router as likes_router
from app.core.config import settings
from app.core.exception_handlers import register_exception_handlers

# 서버 실행 시 INFO 기본 출력 (최소 로깅)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)


async def add_security_headers(request: Request, call_next):
    """보안 헤더 + Process-Time(DEBUG)"""
    response = await call_next(request)
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-Content-Type-Options"] = "nosniff"
    if settings.DEBUG:
        response.headers["X-Process-Time"] = "0"
    return response


@asynccontextmanager
async def lifespan(app: FastAPI):
    """앱 시작/종료 시 DB 연결 관리"""
    from app.core.database import init_database, close_database
    init_database()
    yield
    close_database()


app = FastAPI(
    title="PuppyTalk API",
    description="소규모 커뮤니티 백엔드 API",
    version="1.0.0",
    lifespan=lifespan,
)

# 미들웨어
app.middleware("http")(add_security_headers)

# CORS 설정 (쿠키-세션 인증: allow_credentials=True)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 예외 핸들러 등록
register_exception_handlers(app)

# 업로드 파일 서빙 (upload 폴더 → /upload URL로 접근)
upload_dir = Path(__file__).parent / "upload"
upload_dir.mkdir(exist_ok=True)
app.mount("/upload", StaticFiles(directory=str(upload_dir)), name="upload")

# 라우터 등록
app.include_router(auth_router)
app.include_router(users_router)
app.include_router(posts_router)
app.include_router(comments_router)
app.include_router(likes_router)


@app.get("/")
def root():
    """API 정보"""
    return {
        "code": "OK",
        "data": {
            "message": "PuppyTalk API is running!",
            "version": "1.0.0",
            "docs": "/docs",
        },
    }

