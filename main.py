import logging
import threading
from pathlib import Path

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.core.cleanup import run_once as cleanup_once, run_loop as cleanup_loop
from app.core.config import settings
from app.api.v1 import v1_router
from app.common import ApiCode, ApiResponse, setup_logging
from app.core.exception_handlers import register_exception_handlers
from app.core.middleware import (
    access_log_middleware,
    rate_limit_middleware,
    request_id_middleware,
    security_headers_middleware,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    from app.core.database import init_database, close_database
    setup_logging()
    log = logging.getLogger(__name__)
    if not init_database():
        log.critical("DB 연결 실패로 시작 시 검증 실패. 요청 시점에 재시도됨.")
    else:
        log.info("MySQL 연결 성공.")

    cleanup_once()
    stop_event = threading.Event()
    cleanup_thread = None
    if settings.SESSION_CLEANUP_INTERVAL > 0:
        cleanup_thread = threading.Thread(target=cleanup_loop, args=(stop_event,), daemon=False)
        cleanup_thread.start()

    yield

    stop_event.set()
    if cleanup_thread is not None:
        cleanup_thread.join(timeout=10)
    close_database()


app = FastAPI(
    title="PuppyTalk API",
    description="소규모 커뮤니티 백엔드 API",
    version="1.0.0",
    lifespan=lifespan,
)

app.middleware("http")(security_headers_middleware)
app.middleware("http")(rate_limit_middleware)
app.middleware("http")(access_log_middleware)
app.middleware("http")(request_id_middleware)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

register_exception_handlers(app)

upload_dir = Path(__file__).parent / "upload"
upload_dir.mkdir(exist_ok=True)
app.mount("/upload", StaticFiles(directory=str(upload_dir)), name="upload")

app.include_router(v1_router)


@app.get("/", response_model=ApiResponse)
def root():
    return {
        "code": ApiCode.OK.value,
        "data": {
            "message": "PuppyTalk API is running!",
            "version": "1.0.0",
            "docs": "/docs",
        },
    }


@app.get("/health")
def health():
    from fastapi.responses import JSONResponse
    from app.core.database import check_database
    ok = check_database()
    if ok:
        return JSONResponse(
            status_code=200,
            content={"code": ApiCode.OK.value, "data": {"status": "ok", "database": "connected"}},
        )
    return JSONResponse(
        status_code=503,
        content={"code": ApiCode.DB_ERROR.value, "data": {"status": "degraded", "database": "disconnected"}},
    )
