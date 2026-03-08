# PuppyTalk API 진입점. lifespan, 미들웨어·라우터·/health. DI는 app.api.dependencies.
import asyncio
import logging
from pathlib import Path

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from starlette.middleware.trustedhost import TrustedHostMiddleware

from app.api.v1 import v1_router
from app.common import ApiCode, ApiResponse, setup_logging
from app.common.schema import RootData
from app.core.cleanup import run_loop_async, run_once as cleanup_once
from app.core.config import settings
from app.core.exception_handlers import register_exception_handlers
from app.core.middleware import (
    access_log_middleware,
    proxy_headers_middleware,
    rate_limit_middleware,
    request_id_middleware,
    security_headers_middleware,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    from app.db import init_database, close_database
    from app.infra.redis import close_redis, init_redis

    setup_logging()
    log = logging.getLogger(__name__)
    if not await init_database():
        log.critical("DB 연결 실패로 시작 시 검증 실패. 요청 시점에 재시도됨.")
    else:
        log.info("PostgreSQL 연결 성공.")

    await init_redis(app)

    await cleanup_once()
    stop_event = asyncio.Event()
    cleanup_task = None
    if settings.SESSION_CLEANUP_INTERVAL > 0:
        cleanup_task = asyncio.create_task(run_loop_async(stop_event))

    yield

    stop_event.set()
    if cleanup_task is not None:
        try:
            await asyncio.wait_for(asyncio.shield(cleanup_task), timeout=15.0)
        except asyncio.TimeoutError:
            cleanup_task.cancel()
            try:
                await cleanup_task
            except asyncio.CancelledError:
                pass
    await close_redis(app)
    await close_database()


app = FastAPI(
    title="PuppyTalk API",
    description="커뮤니티 백엔드 API",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
if settings.TRUSTED_HOSTS != ["*"]:
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=settings.TRUSTED_HOSTS)

# async def 미들웨어 유지(BaseHTTPMiddleware는 run_in_executor 오버헤드 있음). 나중에 등록한 것이 요청 시 먼저 실행.
# 실행 순서: proxy_headers(Nginx 등에서 실제 IP 추출) → request_id → access_log → rate_limit → security_headers → 라우트
app.middleware("http")(security_headers_middleware)
app.middleware("http")(rate_limit_middleware)
app.middleware("http")(access_log_middleware)
app.middleware("http")(request_id_middleware)
app.middleware("http")(proxy_headers_middleware)

register_exception_handlers(app)

if settings.STORAGE_BACKEND == "local":
    upload_dir = Path(__file__).resolve().parent.parent / "upload"
    upload_dir.mkdir(exist_ok=True)
    app.mount("/upload", StaticFiles(directory=str(upload_dir)), name="upload")

app.include_router(v1_router)


@app.get("/", response_model=ApiResponse[RootData])
def root():
    return ApiResponse(
        code=ApiCode.OK.value,
        data=RootData(
            message="PuppyTalk API is running!",
            version="1.0.0",
            docs="/docs",
        ),
    )


@app.get("/health")
async def health():
    from fastapi.responses import JSONResponse
    from app.db import check_database

    ok = await check_database()
    if ok:
        return JSONResponse(
            status_code=200,
            content={
                "code": ApiCode.OK.value,
                "data": {"status": "ok", "database": "connected"},
            },
        )
    return JSONResponse(
        status_code=503,
        content={
            "code": ApiCode.DB_ERROR.value,
            "data": {"status": "degraded", "database": "disconnected"},
        },
    )
