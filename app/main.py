# PuppyTalk API 진입점. lifespan, 미들웨어·라우터·/health. DI는 app.api.dependencies.
import asyncio
import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from starlette.middleware.gzip import GZipMiddleware
from starlette.middleware.trustedhost import TrustedHostMiddleware

from app.api.v1 import v1_router
from app.common import ApiCode, ApiResponse, RootData, setup_logging
from app.core.cleanup import run_loop_async
from app.core.cleanup import run_once as cleanup_once
from app.core.config import settings
from app.core.exception_handlers import register_exception_handlers
from app.core.middleware import (
    RequestIdMiddleware,
    access_log_middleware,
    security_headers_middleware,
)
from app.core.middleware.proxy_headers import ProxyHeadersMiddleware
from app.core.middleware.rate_limit import RateLimitMiddleware


@asynccontextmanager
async def lifespan(app: FastAPI):
    from app.db import close_database, init_database
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
        except TimeoutError:
            cleanup_task.cancel()
            try:
                await cleanup_task
            except asyncio.CancelledError:
                pass  # Intended: swallow cancel on lifespan shutdown
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

# LIFO: 마지막 add_middleware가 요청 진입 시 가장 먼저 실행.
# RequestIdMiddleware를 최하단에 등록 → 가장 바깥쪽 껍질이 되어 요청 시 맨 먼저 request_id 발급.
# GZip은 안쪽(코드상 상단)에 두어 IP·Request ID 흐름을 건드리지 않고 응답만 압축.
app.middleware("http")(security_headers_middleware)
app.middleware("http")(access_log_middleware)
app.add_middleware(GZipMiddleware, minimum_size=1024)
app.add_middleware(RateLimitMiddleware)
app.add_middleware(ProxyHeadersMiddleware)
app.add_middleware(RequestIdMiddleware)

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
