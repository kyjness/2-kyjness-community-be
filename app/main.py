# PuppyTalk API 진입점. lifespan, 미들웨어·라우터·/health. DI는 app.api.dependencies.
import asyncio
import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import APIRouter, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.gzip import GZipMiddleware
from starlette.middleware.trustedhost import TrustedHostMiddleware

from app.api.v1 import v1_router
from app.common import ApiCode, ApiResponse, RootData, setup_logging
from app.db import check_database
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


# 1. 설정값 가져오기
_prefix = settings.API_PREFIX.rstrip("/")

app = FastAPI(
    title="PuppyTalk API",
    description="커뮤니티 백엔드 API",
    version="1.0.0",
    lifespan=lifespan,
    # 2. Swagger 및 OpenAPI 경로를 prefix에 맞게 동적 설정
    docs_url=f"{_prefix}/docs",
    redoc_url=f"{_prefix}/redoc",
    openapi_url=f"{_prefix}/openapi.json",
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

# 3. 루트 및 헬스체크용 공통 라우터 생성
base_router = APIRouter(prefix=_prefix)


@base_router.get("/", response_model=ApiResponse[RootData])
def root():
    return ApiResponse(
        code=ApiCode.OK,
        data=RootData(
            message="PuppyTalk API is running!",
            version="1.0.0",
            docs=f"{_prefix}/docs",
        ),
    )


@base_router.get("/health")
async def health():
    ok = await check_database()
    status_code = 200 if ok else 503
    return JSONResponse(
        status_code=status_code,
        content={
            "code": ApiCode.OK.value if ok else ApiCode.DB_ERROR.value,
            "data": {"status": "ok" if ok else "degraded"},
        },
    )


# 4. 라우터 등록 (순서 중요)
app.include_router(base_router)  # /v1, /v1/health 등록
app.include_router(v1_router)  # /v1/auth, /v1/users 등 기존 도메인 등록
