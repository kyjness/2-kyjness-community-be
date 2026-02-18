# app/core/config.py
import os
from pathlib import Path
from typing import List
from dotenv import load_dotenv

# config 파일 기준 프로젝트 루트의 .env 로드 (CWD 무관)
_env_path = Path(__file__).resolve().parent.parent.parent / ".env"
load_dotenv(_env_path)

class Settings:
    
    # 서버 설정
    HOST: str = os.getenv("HOST", "0.0.0.0")
    PORT: int = int(os.getenv("PORT", "8000"))
    DEBUG: bool = os.getenv("DEBUG", "True").lower() == "true"
    
    # CORS 설정 (allow_credentials=True 사용 시 allow_origins는 "*" 금지)
    CORS_ORIGINS: List[str] = [
        origin.strip()
        for origin in os.getenv(
            "CORS_ORIGINS",
            "http://127.0.0.1:5500",
        ).split(",")
        if origin.strip()
    ]
    
    # 세션 설정
    SESSION_EXPIRY_TIME: int = int(os.getenv("SESSION_EXPIRY_TIME", "86400"))  # 24시간
    # 만료 세션 정리 주기(초). 0이면 주기 실행 비활성화(시작 시 1회만 실행)
    SESSION_CLEANUP_INTERVAL: int = int(os.getenv("SESSION_CLEANUP_INTERVAL", "3600"))  # 1시간
    # Set-Cookie secure: True면 HTTPS에서만 쿠키 전송. 배포(HTTPS) 시 True 권장
    COOKIE_SECURE: bool = os.getenv("COOKIE_SECURE", "false").lower() == "true"

    # Rate limit 분산 저장소. 비우면 인메모리(워커별). 설정 시 Redis 사용(워커/인스턴스 공통)
    REDIS_URL: str = os.getenv("REDIS_URL", "").strip()

    # Rate limiting (IP당 RATE_LIMIT_WINDOW 초 동안 RATE_LIMIT_MAX_REQUESTS 초과 시 429)
    RATE_LIMIT_WINDOW: int = int(os.getenv("RATE_LIMIT_WINDOW", "60"))
    RATE_LIMIT_MAX_REQUESTS: int = int(os.getenv("RATE_LIMIT_MAX_REQUESTS", "100"))
    # 로그인 전용 (브루트포스 방지): IP당 분당 시도 횟수 제한
    LOGIN_RATE_LIMIT_WINDOW: int = int(os.getenv("LOGIN_RATE_LIMIT_WINDOW", "60"))
    LOGIN_RATE_LIMIT_MAX_ATTEMPTS: int = int(os.getenv("LOGIN_RATE_LIMIT_MAX_ATTEMPTS", "5"))

    # 파일 업로드 설정
    MAX_FILE_SIZE: int = int(os.getenv("MAX_FILE_SIZE", "10485760"))  # 10MB
    ALLOWED_IMAGE_TYPES: List[str] = [
        img_type.strip()
        for img_type in os.getenv("ALLOWED_IMAGE_TYPES", "image/jpeg,image/jpg,image/png").split(",")
        if img_type.strip()
    ]
    
    # API 기본 URL (파일 업로드 URL 생성용, local 저장 시 사용)
    BE_API_URL: str = os.getenv("BE_API_URL", "http://127.0.0.1:8000")

    # 파일 저장소: "local" = upload 폴더, "s3" = AWS S3 (배포 시 권장)
    STORAGE_BACKEND: str = os.getenv("STORAGE_BACKEND", "local")
    # S3 사용 시 필수
    S3_BUCKET_NAME: str = os.getenv("S3_BUCKET_NAME", "")
    AWS_REGION: str = os.getenv("AWS_REGION", "ap-northeast-2")
    AWS_ACCESS_KEY_ID: str = os.getenv("AWS_ACCESS_KEY_ID", "")
    AWS_SECRET_ACCESS_KEY: str = os.getenv("AWS_SECRET_ACCESS_KEY", "")
    # S3 객체 공개 URL 접두사. 비우면 https://{bucket}.s3.{region}.amazonaws.com/ 사용
    S3_PUBLIC_BASE_URL: str = os.getenv("S3_PUBLIC_BASE_URL", "")

    # 로깅 (레벨: DEBUG, INFO, WARNING, ERROR / 파일 비우면 콘솔만)
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO").upper()
    LOG_FILE_PATH: str = os.getenv("LOG_FILE_PATH", "").strip()

    # MySQL 설정 (puppytalk)
    DB_HOST: str = os.getenv("DB_HOST", "localhost")
    DB_PORT: int = int(os.getenv("DB_PORT", "3306"))
    DB_USER: str = os.getenv("DB_USER", "root")
    DB_PASSWORD: str = os.getenv("DB_PASSWORD", "")
    DB_NAME: str = os.getenv("DB_NAME", "puppytalk")


# 전역 설정 인스턴스
settings = Settings()
