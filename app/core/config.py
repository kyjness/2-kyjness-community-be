# app/core/config.py
import os
from pathlib import Path
from typing import List
from dotenv import load_dotenv

# config 파일 기준 프로젝트 루트의 .env 로드 (CWD 무관)
_env_path = Path(__file__).resolve().parent.parent.parent / ".env"
load_dotenv(_env_path)

class Settings:
    """애플리케이션 설정 관리"""
    
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

    # 파일 업로드 설정
    MAX_FILE_SIZE: int = int(os.getenv("MAX_FILE_SIZE", "10485760"))  # 10MB
    ALLOWED_IMAGE_TYPES: List[str] = [
        img_type.strip() 
        for img_type in os.getenv("ALLOWED_IMAGE_TYPES", "image/jpeg,image/jpg,image/png").split(",")
    ]
    
    # API 기본 URL (파일 업로드 URL 생성용)
    BE_API_URL: str = os.getenv("BE_API_URL", "http://localhost:8000")

    # MySQL 설정 (puppytalk)
    DB_HOST: str = os.getenv("DB_HOST", "localhost")
    DB_PORT: int = int(os.getenv("DB_PORT", "3306"))
    DB_USER: str = os.getenv("DB_USER", "root")
    DB_PASSWORD: str = os.getenv("DB_PASSWORD", "")
    DB_NAME: str = os.getenv("DB_NAME", "puppytalk")


# 전역 설정 인스턴스
settings = Settings()
