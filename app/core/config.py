# 환경 변수 (Settings). ENV에 따라 .env.{ENV} 만 로드. 단일 .env 미사용.
# 주의: app.common 등 상위 패키지 import 시 Alembic env 로드 시 순환 참조 발생 → config는 독립 유지.
import os
from pathlib import Path
from typing import List
from dotenv import load_dotenv

_env = os.getenv("ENV", "development")
_root = Path(__file__).resolve().parent.parent.parent
_env_file = _root / f".env.{_env}"
if _env_file.exists():
    load_dotenv(_env_file)


class Settings:
    # 서버
    HOST: str = os.getenv("HOST", "0.0.0.0")
    PORT: int = int(os.getenv("PORT", "8000"))
    DEBUG: bool = os.getenv("DEBUG", "True").lower() == "true"
    # CORS (허용 Origin 목록, 쉼표 구분. Vite(React) 개발 서버 5173)
    CORS_ORIGINS: List[str] = [
        origin.strip()
        for origin in os.getenv(
            "CORS_ORIGINS",
            "http://127.0.0.1:5173,http://localhost:5173",
        ).split(",")
        if origin.strip()
    ]
    # 세션 (만료 시간 초, cleanup 주기 초)
    SESSION_EXPIRY_TIME: int = int(os.getenv("SESSION_EXPIRY_TIME", "86400"))
    SESSION_CLEANUP_INTERVAL: int = int(os.getenv("SESSION_CLEANUP_INTERVAL", "3600"))
    COOKIE_SECURE: bool = os.getenv("COOKIE_SECURE", "false").lower() == "true"
    # JWT (Access/Refresh). 배포 시 JWT_SECRET_KEY 반드시 변경.
    JWT_SECRET_KEY: str = os.getenv("JWT_SECRET_KEY", "change-me-in-production")
    JWT_ALGORITHM: str = os.getenv("JWT_ALGORITHM", "HS256")
    ACCESS_TOKEN_EXPIRE_SECONDS: int = int(os.getenv("ACCESS_TOKEN_EXPIRE_SECONDS", "900"))
    REFRESH_TOKEN_EXPIRE_DAYS: int = int(os.getenv("REFRESH_TOKEN_EXPIRE_DAYS", "7"))
    REFRESH_TOKEN_COOKIE_NAME: str = os.getenv("REFRESH_TOKEN_COOKIE_NAME", "refresh_token")
    # Redis (Rate Limit 분산. 비우면 연결 시도 안 함, 미들웨어는 Fail-open)
    REDIS_URL: str = os.getenv("REDIS_URL", "").strip()
    REDIS_MAX_CONNECTIONS: int = int(os.getenv("REDIS_MAX_CONNECTIONS", "20"))
    # Proxy·Trusted Host. TRUST_X_FORWARDED_FOR=True면 X-Forwarded-For 첫 값으로 request.client 보정. TRUSTED_HOSTS=* 이면 미등록
    TRUST_X_FORWARDED_FOR: bool = os.getenv("TRUST_X_FORWARDED_FOR", "false").lower() == "true"
    # 신뢰 프록시 IP/CIDR. 비어 있으면 TRUST_X_FORWARDED_FOR=True일 때 모든 요청에서 X-Forwarded-For 파싱. 설정 시 해당 대역에서 온 요청만 파싱(IP 스푸핑 방어). 예: 10.0.0.0/8,172.16.0.0/12
    TRUSTED_PROXY_IPS: List[str] = [
        h.strip() for h in os.getenv("TRUSTED_PROXY_IPS", "").strip().split(",") if h.strip()
    ]
    TRUSTED_HOSTS: List[str] = [
        h.strip() for h in os.getenv("TRUSTED_HOSTS", "*").split(",") if h.strip()
    ]
    # Rate limit (전역: 창 길이 초, 최대 요청 수 / 로그인: 창·최대 시도)
    RATE_LIMIT_WINDOW: int = int(os.getenv("RATE_LIMIT_WINDOW", "60"))
    RATE_LIMIT_MAX_REQUESTS: int = int(os.getenv("RATE_LIMIT_MAX_REQUESTS", "100"))
    LOGIN_RATE_LIMIT_WINDOW: int = int(os.getenv("LOGIN_RATE_LIMIT_WINDOW", "60"))
    LOGIN_RATE_LIMIT_MAX_ATTEMPTS: int = int(os.getenv("LOGIN_RATE_LIMIT_MAX_ATTEMPTS", "5"))
    # 회원가입용 이미지 (토큰 TTL 초, IP당 업로드 rate limit; MAX=1이면 두 번째 signup 시 업로드만 429되고 /auth/signup 요청 안 나감)
    SIGNUP_IMAGE_TOKEN_TTL_SECONDS: int = int(os.getenv("SIGNUP_IMAGE_TOKEN_TTL_SECONDS", "3600"))
    SIGNUP_UPLOAD_RATE_LIMIT_WINDOW: int = int(os.getenv("SIGNUP_UPLOAD_RATE_LIMIT_WINDOW", "3600"))
    SIGNUP_UPLOAD_RATE_LIMIT_MAX: int = int(os.getenv("SIGNUP_UPLOAD_RATE_LIMIT_MAX", "10"))
    # 파일 업로드 (최대 바이트, 허용 content-type)
    MAX_FILE_SIZE: int = int(os.getenv("MAX_FILE_SIZE", "10485760"))
    ALLOWED_IMAGE_TYPES: List[str] = [
        img_type.strip()
        for img_type in os.getenv("ALLOWED_IMAGE_TYPES", "image/jpeg,image/png").split(",")
        if img_type.strip()
    ]
    BE_API_URL: str = os.getenv("BE_API_URL", "http://127.0.0.1:8000")
    # 스토리지 (local | S3, S3 시 버킷·리전·키·공개 URL)
    STORAGE_BACKEND: str = os.getenv("STORAGE_BACKEND", "local")
    S3_BUCKET_NAME: str = os.getenv("S3_BUCKET_NAME", "")
    AWS_REGION: str = os.getenv("AWS_REGION", "ap-northeast-2")
    AWS_ACCESS_KEY_ID: str = os.getenv("AWS_ACCESS_KEY_ID", "")
    AWS_SECRET_ACCESS_KEY: str = os.getenv("AWS_SECRET_ACCESS_KEY", "")
    S3_PUBLIC_BASE_URL: str = os.getenv("S3_PUBLIC_BASE_URL", "")
    # 로깅 (레벨, 파일 경로, 슬로우 요청 임계치 ms)
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO").upper()
    LOG_FILE_PATH: str = os.getenv("LOG_FILE_PATH", "").strip()
    SLOW_REQUEST_MS: int = int(os.getenv("SLOW_REQUEST_MS", "1000"))
    # 보안 헤더 (HSTS, Referrer-Policy, Permissions-Policy, CSP)
    HSTS_ENABLED: bool = os.getenv("HSTS_ENABLED", "false").lower() == "true"
    HSTS_MAX_AGE: int = int(os.getenv("HSTS_MAX_AGE", "31536000"))
    REFERRER_POLICY: str = os.getenv("REFERRER_POLICY", "strict-origin-when-cross-origin")
    PERMISSIONS_POLICY: str = os.getenv("PERMISSIONS_POLICY", "geolocation=(), microphone=(), camera=()")
    CONTENT_SECURITY_POLICY: str = os.getenv(
        "CONTENT_SECURITY_POLICY",
        "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; frame-ancestors 'none'; base-uri 'self'; form-action 'self';",
    ).strip()
    # DB (연결 정보, /health ping 타임아웃 초). WRITER/READER 비우면 DB_* 로 단일 URL 사용
    DB_PING_TIMEOUT: int = int(os.getenv("DB_PING_TIMEOUT", "1"))
    DB_POOL_SIZE: int = int(os.getenv("DB_POOL_SIZE", "20"))
    DB_MAX_OVERFLOW: int = int(os.getenv("DB_MAX_OVERFLOW", "10"))
    DB_POOL_RECYCLE: int = int(os.getenv("DB_POOL_RECYCLE", "3600"))
    DB_HOST: str = os.getenv("DB_HOST", "localhost")
    DB_PORT: int = int(os.getenv("DB_PORT", "3306"))
    DB_USER: str = os.getenv("DB_USER", "root")
    DB_PASSWORD: str = os.getenv("DB_PASSWORD", "")
    DB_NAME: str = os.getenv("DB_NAME", "puppytalk")
    WRITER_DB_URL: str = os.getenv("WRITER_DB_URL", "").strip()
    READER_DB_URL: str = os.getenv("READER_DB_URL", "").strip()


settings = Settings()
