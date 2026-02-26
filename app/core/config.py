import os
from pathlib import Path
from typing import List
from dotenv import load_dotenv

_env = os.getenv("ENV", "development")
_root = Path(__file__).resolve().parent.parent.parent
_env_file = _root / f".env.{_env}"
if _env_file.exists():
    load_dotenv(_env_file)
else:
    load_dotenv(_root / ".env")


class Settings:
    # 서버
    HOST: str = os.getenv("HOST", "0.0.0.0")
    PORT: int = int(os.getenv("PORT", "8000"))
    DEBUG: bool = os.getenv("DEBUG", "True").lower() == "true"
    # CORS (허용 Origin 목록, 쉼표 구분)
    CORS_ORIGINS: List[str] = [
        origin.strip()
        for origin in os.getenv(
            "CORS_ORIGINS",
            "http://127.0.0.1:5500",
        ).split(",")
        if origin.strip()
    ]
    # 세션 (만료 시간 초, cleanup 주기 초)
    SESSION_EXPIRY_TIME: int = int(os.getenv("SESSION_EXPIRY_TIME", "86400"))
    SESSION_CLEANUP_INTERVAL: int = int(os.getenv("SESSION_CLEANUP_INTERVAL", "3600"))
    COOKIE_SECURE: bool = os.getenv("COOKIE_SECURE", "false").lower() == "true"
    # Rate limit (전역: 창 길이 초, 최대 요청 수 / 로그인: 창·최대 시도)
    # 프록시(ALB/Nginx) 뒤에서만 True. 직접 노출 시 클라이언트가 X-Forwarded-For 위조 가능
    TRUST_X_FORWARDED_FOR: bool = os.getenv("TRUST_X_FORWARDED_FOR", "false").lower() == "true"
    RATE_LIMIT_WINDOW: int = int(os.getenv("RATE_LIMIT_WINDOW", "60"))
    RATE_LIMIT_MAX_REQUESTS: int = int(os.getenv("RATE_LIMIT_MAX_REQUESTS", "100"))
    LOGIN_RATE_LIMIT_WINDOW: int = int(os.getenv("LOGIN_RATE_LIMIT_WINDOW", "60"))
    LOGIN_RATE_LIMIT_MAX_ATTEMPTS: int = int(os.getenv("LOGIN_RATE_LIMIT_MAX_ATTEMPTS", "5"))
    # 회원가입용 이미지 (토큰 TTL 초, IP당 업로드 rate limit)
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
    # 보안 헤더 (HSTS, Referrer-Policy, Permissions-Policy)
    HSTS_ENABLED: bool = os.getenv("HSTS_ENABLED", "false").lower() == "true"
    HSTS_MAX_AGE: int = int(os.getenv("HSTS_MAX_AGE", "31536000"))
    REFERRER_POLICY: str = os.getenv("REFERRER_POLICY", "strict-origin-when-cross-origin")
    PERMISSIONS_POLICY: str = os.getenv("PERMISSIONS_POLICY", "geolocation=(), microphone=(), camera=()")
    # DB (연결 정보, /health ping 타임아웃 초)
    DB_PING_TIMEOUT: int = int(os.getenv("DB_PING_TIMEOUT", "1"))
    DB_HOST: str = os.getenv("DB_HOST", "localhost")
    DB_PORT: int = int(os.getenv("DB_PORT", "3306"))
    DB_USER: str = os.getenv("DB_USER", "root")
    DB_PASSWORD: str = os.getenv("DB_PASSWORD", "")
    DB_NAME: str = os.getenv("DB_NAME", "puppytalk")


settings = Settings()
