# main.py
import logging
import time
from logging.handlers import RotatingFileHandler
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
from app.core.config import settings
from app.core.exception_handlers import register_exception_handlers
from app.core.rate_limit import rate_limit_middleware
from app.core.response import ApiResponse

# 로깅 설정: 레벨·포맷·파일(선택)
_LOG_FMT = "%(asctime)s - %(levelname)s - %(name)s - %(message)s"
_LOG_DATEFMT = "%Y-%m-%d %H:%M:%S"


def _setup_logging() -> None:
    level = getattr(logging, settings.LOG_LEVEL, logging.INFO)
    root = logging.getLogger()
    root.setLevel(level)
    root.handlers.clear()
    console = logging.StreamHandler()
    console.setFormatter(logging.Formatter(_LOG_FMT, datefmt=_LOG_DATEFMT))
    root.addHandler(console)
    if settings.LOG_FILE_PATH:
        log_path = Path(settings.LOG_FILE_PATH)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        file_handler = RotatingFileHandler(
            log_path,
            maxBytes=5 * 1024 * 1024,  # 5MB
            backupCount=5,
            encoding="utf-8",
        )
        file_handler.setFormatter(logging.Formatter(_LOG_FMT, datefmt=_LOG_DATEFMT))
        logging.getLogger().addHandler(file_handler)


_setup_logging()
_access_logger = logging.getLogger("app.access")


async def access_log_middleware(request: Request, call_next):
    """모든 HTTP 요청에 대해 Method, Path, Status, 소요 시간(ms) 로깅."""
    start = time.perf_counter()
    response = await call_next(request)
    duration_ms = (time.perf_counter() - start) * 1000
    client = request.client.host if request.client else "-"
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        client = forwarded.split(",")[0].strip()
    _access_logger.info(
        "%s %s %s %.2fms %s",
        request.method,
        request.url.path,
        response.status_code,
        duration_ms,
        client,
    )
    return response


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

# 미들웨어 (아래서부터 실행: rate_limit → access_log → CORS → security_headers)
app.middleware("http")(rate_limit_middleware)
app.middleware("http")(access_log_middleware)
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


@app.get("/", response_model=ApiResponse)
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

