# 환경 변수 (Settings). 로컬 실행 시 프로젝트 루트 .env 로드. 배포 시에는 infra의 .env 또는 컨테이너 환경으로 주입.
# 주의: app.common 등 상위 패키지 import 시 Alembic env 로드 시 순환 참조 발생 → config는 독립 유지.
import os
from pathlib import Path

from dotenv import load_dotenv

_root = Path(__file__).resolve().parent.parent.parent
_env_file = _root / ".env"
if _env_file.exists():
    load_dotenv(_env_file)


class Settings:
    # ----- 서버 (노출 주소·CORS·디버그) -----
    HOST: str = os.getenv("HOST", "0.0.0.0")
    PORT: int = int(os.getenv("PORT", "8000"))
    BE_API_URL: str = os.getenv("BE_API_URL", "http://localhost:8000")
    DEBUG: bool = os.getenv("DEBUG", "True").lower() == "true"
    CORS_ORIGINS: list[str] = [
        origin.strip()
        for origin in os.getenv(
            "CORS_ORIGINS",
            "https://puppytalk.shop,http://127.0.0.1:5173,http://localhost:5173",
        ).split(",")
        if origin.strip()
    ]
    API_PREFIX: str = "/v1"  # Nginx location /v1/ 과 일치

    # ----- DB (WRITER/READER 비우면 DB_* 로 단일 URL 사용) -----
    DB_HOST: str = os.getenv("DB_HOST", "postgres")
    DB_PORT: int = int(os.getenv("DB_PORT", "5432"))
    DB_USER: str = os.getenv("DB_USER", "postgres")
    DB_PASSWORD: str = os.getenv("DB_PASSWORD", "")
    DB_NAME: str = os.getenv("DB_NAME", "puppytalk")
    DB_POOL_SIZE: int = int(os.getenv("DB_POOL_SIZE", "20"))
    DB_MAX_OVERFLOW: int = int(os.getenv("DB_MAX_OVERFLOW", "10"))
    DB_POOL_RECYCLE: int = int(os.getenv("DB_POOL_RECYCLE", "3600"))
    DB_PING_TIMEOUT: int = int(os.getenv("DB_PING_TIMEOUT", "1"))
    WRITER_DB_URL: str = os.getenv("WRITER_DB_URL", "").strip()
    READER_DB_URL: str = os.getenv("READER_DB_URL", "").strip()
    DB_INIT_MAX_ATTEMPTS: int = max(1, int(os.getenv("DB_INIT_MAX_ATTEMPTS", "3")))
    DB_INIT_RETRY_DELAY_SECONDS: float = float(os.getenv("DB_INIT_RETRY_DELAY_SECONDS", "2"))

    # ----- JWT (배포 시 JWT_SECRET_KEY 반드시 변경) -----
    JWT_SECRET_KEY: str = os.getenv("JWT_SECRET_KEY", "change-me-in-production")
    JWT_ALGORITHM: str = os.getenv("JWT_ALGORITHM", "HS256")
    ACCESS_TOKEN_EXPIRE_SECONDS: int = int(os.getenv("ACCESS_TOKEN_EXPIRE_SECONDS", "1800"))
    REFRESH_TOKEN_EXPIRE_DAYS: int = int(os.getenv("REFRESH_TOKEN_EXPIRE_DAYS", "7"))
    REFRESH_TOKEN_COOKIE_NAME: str = os.getenv("REFRESH_TOKEN_COOKIE_NAME", "refresh_token")
    COOKIE_SECURE: bool = os.getenv("COOKIE_SECURE", "false").lower() == "true"

    # ----- 회원가입 임시 이미지 TTL 정리 (주기 초. 0이면 백그라운드 루프 비활성, 시작 시 1회는 항상 실행) -----
    SIGNUP_IMAGE_CLEANUP_INTERVAL: int = int(os.getenv("SIGNUP_IMAGE_CLEANUP_INTERVAL", "3600"))

    # ----- Redis (비우면 연결 시도 안 함, rate limit 등 Fail-open) -----
    REDIS_URL: str = os.getenv("REDIS_URL", "").strip()
    REDIS_MAX_CONNECTIONS: int = int(os.getenv("REDIS_MAX_CONNECTIONS", "20"))
    # POST /posts 멱등성: 성공 응답 캐시 TTL, in-flight 잠금 TTL(초)
    IDEMPOTENCY_POST_CREATE_TTL_SECONDS: int = max(
        60, int(os.getenv("IDEMPOTENCY_POST_CREATE_TTL_SECONDS", "3600"))
    )
    IDEMPOTENCY_POST_CREATE_LOCK_TTL_SECONDS: int = max(
        5, int(os.getenv("IDEMPOTENCY_POST_CREATE_LOCK_TTL_SECONDS", "120"))
    )
    # POST /media/images* 멱등성 (업로드 지연 대비 잠금 TTL 여유)
    IDEMPOTENCY_MEDIA_UPLOAD_TTL_SECONDS: int = max(
        60, int(os.getenv("IDEMPOTENCY_MEDIA_UPLOAD_TTL_SECONDS", "3600"))
    )
    IDEMPOTENCY_MEDIA_UPLOAD_LOCK_TTL_SECONDS: int = max(
        30, int(os.getenv("IDEMPOTENCY_MEDIA_UPLOAD_LOCK_TTL_SECONDS", "60"))
    )

    # ----- Proxy·Trusted Host (Nginx/ALB 뒤 배포 시) -----
    TRUST_X_FORWARDED_FOR: bool = os.getenv("TRUST_X_FORWARDED_FOR", "false").lower() == "true"
    TRUSTED_PROXY_IPS: list[str] = [
        h.strip() for h in os.getenv("TRUSTED_PROXY_IPS", "").strip().split(",") if h.strip()
    ]
    TRUSTED_HOSTS: list[str] = [
        h.strip() for h in os.getenv("TRUSTED_HOSTS", "*").split(",") if h.strip()
    ]

    # ----- Rate limit -----
    RATE_LIMIT_WINDOW: int = int(os.getenv("RATE_LIMIT_WINDOW", "60"))
    RATE_LIMIT_MAX_REQUESTS: int = int(os.getenv("RATE_LIMIT_MAX_REQUESTS", "100"))
    LOGIN_RATE_LIMIT_WINDOW: int = int(os.getenv("LOGIN_RATE_LIMIT_WINDOW", "60"))
    LOGIN_RATE_LIMIT_MAX_ATTEMPTS: int = int(os.getenv("LOGIN_RATE_LIMIT_MAX_ATTEMPTS", "5"))

    # ----- 회원가입 이미지 (토큰 TTL, IP당 업로드 rate limit) -----
    SIGNUP_IMAGE_TOKEN_TTL_SECONDS: int = int(os.getenv("SIGNUP_IMAGE_TOKEN_TTL_SECONDS", "3600"))
    SIGNUP_UPLOAD_RATE_LIMIT_WINDOW: int = int(os.getenv("SIGNUP_UPLOAD_RATE_LIMIT_WINDOW", "3600"))
    SIGNUP_UPLOAD_RATE_LIMIT_MAX: int = int(os.getenv("SIGNUP_UPLOAD_RATE_LIMIT_MAX", "10"))

    # ----- 파일 업로드 (최대 바이트, 허용 content-type) -----
    MAX_FILE_SIZE: int = int(os.getenv("MAX_FILE_SIZE", "20971520"))
    ALLOWED_IMAGE_TYPES: list[str] = [
        img_type.strip()
        for img_type in os.getenv("ALLOWED_IMAGE_TYPES", "image/jpeg,image/png").split(",")
        if img_type.strip()
    ]

    # ----- 스토리지 (local | s3. s3 시 MinIO/AWS S3) -----
    STORAGE_BACKEND: str = os.getenv("STORAGE_BACKEND", "local")
    S3_BUCKET_NAME: str = os.getenv("S3_BUCKET_NAME", "")
    S3_ENDPOINT_URL: str = os.getenv("S3_ENDPOINT_URL", "").strip()
    AWS_REGION: str = os.getenv("AWS_REGION", "ap-northeast-2")
    AWS_ACCESS_KEY_ID: str = os.getenv("AWS_ACCESS_KEY_ID", "")
    AWS_SECRET_ACCESS_KEY: str = os.getenv("AWS_SECRET_ACCESS_KEY", "")
    S3_PUBLIC_BASE_URL: str = os.getenv("S3_PUBLIC_BASE_URL", "")

    # ----- 로깅 -----
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO").upper()
    LOG_FILE_PATH: str = os.getenv("LOG_FILE_PATH", "").strip()
    SLOW_REQUEST_MS: int = int(os.getenv("SLOW_REQUEST_MS", "1000"))

    # ----- 보안 헤더 (HSTS, Referrer-Policy, CSP 등) -----
    HSTS_ENABLED: bool = os.getenv("HSTS_ENABLED", "false").lower() == "true"
    HSTS_MAX_AGE: int = int(os.getenv("HSTS_MAX_AGE", "31536000"))
    REFERRER_POLICY: str = os.getenv("REFERRER_POLICY", "strict-origin-when-cross-origin")
    PERMISSIONS_POLICY: str = os.getenv(
        "PERMISSIONS_POLICY", "geolocation=(), microphone=(), camera=()"
    )
    CONTENT_SECURITY_POLICY: str = os.getenv(
        "CONTENT_SECURITY_POLICY",
        "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; frame-ancestors 'none'; base-uri 'self'; form-action 'self';",
    ).strip()

    # ----- 신고·블라인드 (Phase 2) -----
    REPORT_BLIND_THRESHOLD: int = int(os.getenv("REPORT_BLIND_THRESHOLD", "5"))

    # ----- 조회수 Write-behind (Redis HINCRBY → 주기적 DB flush) -----
    VIEW_BUFFER_FLUSH_INTERVAL_SECONDS: int = max(
        60, int(os.getenv("VIEW_BUFFER_FLUSH_INTERVAL_SECONDS", "300"))
    )
    VIEW_FLUSH_LOCK_SECONDS: int = max(30, int(os.getenv("VIEW_FLUSH_LOCK_SECONDS", "120")))


settings = Settings()
