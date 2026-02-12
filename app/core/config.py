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
            "http://localhost:3000,http://127.0.0.1:3000,http://localhost:5500,http://127.0.0.1:5500",
        ).split(",")
        if origin.strip()
    ]
    
    # 세션 설정
    SESSION_EXPIRY_TIME: int = int(os.getenv("SESSION_EXPIRY_TIME", "86400"))  # 24시간

    # Rate limiting (추후 미들웨어 등에서 사용 시 참조)
    RATE_LIMIT_WINDOW: int = int(os.getenv("RATE_LIMIT_WINDOW", "60"))
    RATE_LIMIT_MAX_REQUESTS: int = int(os.getenv("RATE_LIMIT_MAX_REQUESTS", "100"))

    # 파일 업로드 설정
    MAX_FILE_SIZE: int = int(os.getenv("MAX_FILE_SIZE", "10485760"))  # 10MB
    MAX_VIDEO_SIZE: int = int(os.getenv("MAX_VIDEO_SIZE", "52428800"))  # 50MB
    ALLOWED_IMAGE_TYPES: List[str] = [
        img_type.strip()
        for img_type in os.getenv("ALLOWED_IMAGE_TYPES", "image/jpeg,image/jpg,image/png").split(",")
        if img_type.strip()
    ]
    ALLOWED_VIDEO_TYPES: List[str] = [
        v.strip()
        for v in os.getenv("ALLOWED_VIDEO_TYPES", "video/mp4,video/webm").split(",")
        if v.strip()
    ]
    
    # API 기본 URL (파일 업로드 URL 생성용, local 저장 시 사용)
    BE_API_URL: str = os.getenv("BE_API_URL", "http://localhost:8000")

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
