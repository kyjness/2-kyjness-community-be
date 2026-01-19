# main.py
import time
import logging
from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from app.auth.auth_route import router as auth_router
from app.users.users_route import router as users_router
from app.posts.posts_route import router as posts_router
from app.comments.comments_route import router as comments_router
from app.likes.likes_route import router as likes_router
from config import settings

# 로깅 설정 (현업 필수)
logging.basicConfig(
    level=logging.INFO if settings.DEBUG else logging.WARNING,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="PuppyTalk API",
    description="커뮤니티 백엔드 API",
    version="1.0.0"
)

@app.middleware("http")
async def global_policy_middleware(request: Request, call_next):
    """전역 공통 정책 미들웨어.

    - 전역 Rate Limiting (가능한 빨리 차단)
    - 요청 처리 시간 측정 (X-Process-Time 헤더)
    """
    start_time = time.perf_counter()

    # 문서/헬스체크/정적 리소스 등은 전역 Rate Limiting 대상에서 제외
    path = request.url.path
    skip_prefixes = ("/docs", "/redoc", "/openapi.json", "/public")
    skip_exact = {"/", "/health"}

    if path not in skip_exact and not path.startswith(skip_prefixes):
        # 로컬 개발/학습용: 간단히 IP 기반으로 제한
        # (리버스 프록시 환경이면 X-Forwarded-For를 고려해야 함)
        client_ip = request.client.host if request.client else "unknown"

        from app.auth.auth_model import AuthModel  # 순환 import 방지용 지연 import

        if not AuthModel.check_rate_limit(client_ip):
            logger.warning(f"Rate limit exceeded: IP={client_ip}, Path={path}")
            response = JSONResponse(
                status_code=429,
                content={"code": "RATE_LIMIT_EXCEEDED", "data": None},
            )
            response.headers["X-Process-Time"] = str(time.perf_counter() - start_time)
            return response

    response = await call_next(request)
    response.headers["X-Process-Time"] = str(time.perf_counter() - start_time)
    return response

# CORS 설정 (프론트엔드와 연결할 때 필요)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 전역 예외 핸들러
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """요청 검증 오류 처리"""
    logger.warning(f"Validation error: Path={request.url.path}, Errors={exc.errors()}")
    return JSONResponse(
        status_code=400,
        content={"code": "INVALID_REQUEST_BODY", "data": None}
    )

@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    """HTTP 예외 처리"""
    # 보안 관련 에러는 WARNING 레벨로 로깅 (인증 실패, 권한 오류 등)
    if exc.status_code in (401, 403):
        logger.warning(f"Security error: Status={exc.status_code}, Path={request.url.path}, Detail={exc.detail}")
    # 4xx 에러는 INFO 레벨로 로깅
    elif 400 <= exc.status_code < 500:
        logger.info(f"Client error: Status={exc.status_code}, Path={request.url.path}, Detail={exc.detail}")
    
    # HTTP 상태 코드는 그대로 유지하면서, 응답 포맷만 통일
    if isinstance(exc.detail, dict):
        return JSONResponse(status_code=exc.status_code, content=exc.detail)
    # detail이 문자열인 경우 (일반적인 HTTPException)
    return JSONResponse(
        status_code=exc.status_code,
        content={"code": str(exc.detail) if exc.detail else "HTTP_ERROR", "data": None}
    )

@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    """일반 예외 처리"""
    logger.error(f"Unhandled exception: Path={request.url.path}, Exception={type(exc).__name__}: {str(exc)}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"code": "INTERNAL_SERVER_ERROR", "data": None}
    )

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

