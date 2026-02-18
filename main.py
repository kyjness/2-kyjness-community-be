# main.py
import logging
import threading
import time
from logging.handlers import RotatingFileHandler
from pathlib import Path

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from starlette.requests import Request

from app.core.config import settings
from app.api.v1 import v1_router
from app.core.codes import ApiCode
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
    if settings.DEBUG:
        response.headers["X-Process-Time"] = f"{duration_ms:.2f}"
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
    """보안 헤더 (X-Frame-Options, X-Content-Type-Options)."""
    response = await call_next(request)
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-Content-Type-Options"] = "nosniff"
    return response


def _run_session_cleanup():
    """만료된 세션 삭제. 동기 함수라 스레드에서 호출."""
    try:
        from app.auth.auth_model import AuthModel
        n = AuthModel.cleanup_expired_sessions()
        if n and n > 0:
            logging.getLogger(__name__).info("Session cleanup: removed %d expired session(s)", n)
    except Exception as e:
        logging.getLogger(__name__).warning("Session cleanup failed: %s", e)


def _session_cleanup_loop():
    """백그라운드 스레드: SESSION_CLEANUP_INTERVAL 마다 만료 세션 정리."""
    interval = max(60, settings.SESSION_CLEANUP_INTERVAL)
    while True:
        time.sleep(interval)
        _run_session_cleanup()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """앱 시작/종료 시 DB 연결 관리 + 만료 세션 정리(1회 및 주기 실행)"""
    from app.core.database import init_database, close_database
    init_database()

    # 시작 시 1회 만료 세션 정리
    _run_session_cleanup()

    # 주기 정리 (INTERVAL > 0 이면 백그라운드 스레드)
    cleanup_thread = None
    if settings.SESSION_CLEANUP_INTERVAL > 0:
        cleanup_thread = threading.Thread(target=_session_cleanup_loop, daemon=True)
        cleanup_thread.start()

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

# API v1 라우터 등록
app.include_router(v1_router)


@app.get("/", response_model=ApiResponse)
def root():
    """API 정보"""
    return {
        "code": ApiCode.OK.value,
        "data": {
            "message": "PuppyTalk API is running!",
            "version": "1.0.0",
            "docs": "/docs",
        },
    }


@app.get("/health", response_model=ApiResponse)
def health():
    """헬스 체크. 로드밸런서/모니터링용. 항상 200."""
    return {"code": ApiCode.OK.value, "data": {"status": "ok"}}

