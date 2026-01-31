# app/core/config.py
import os
from typing import List
from dotenv import load_dotenv

# .env 파일 로드
load_dotenv()

class Settings:
    """애플리케이션 설정 관리"""
    
    # 서버 설정
    HOST: str = os.getenv("HOST", "0.0.0.0")
    PORT: int = int(os.getenv("PORT", "8000"))
    DEBUG: bool = os.getenv("DEBUG", "True").lower() == "true"
    
    # CORS 설정
    CORS_ORIGINS: List[str] = [origin.strip() for origin in os.getenv("CORS_ORIGINS", "*").split(",")]
    
    # 세션 설정
    SESSION_EXPIRY_TIME: int = int(os.getenv("SESSION_EXPIRY_TIME", "86400"))  # 24시간
    
    # Rate Limiting (PROD에서만 활성화 권장. 로컬/과제 시 비활성화)
    RATE_LIMIT_ENABLED: bool = os.getenv("RATE_LIMIT_ENABLED", "false").lower() == "true"
    RATE_LIMIT_WINDOW: int = int(os.getenv("RATE_LIMIT_WINDOW", "60"))  # 60초
    RATE_LIMIT_MAX_REQUESTS: int = int(os.getenv("RATE_LIMIT_MAX_REQUESTS", "10"))  # 최대 10회
    
    # 파일 업로드 설정
    MAX_FILE_SIZE: int = int(os.getenv("MAX_FILE_SIZE", "10485760"))  # 10MB (바이트)
    ALLOWED_IMAGE_TYPES: List[str] = [img_type.strip() for img_type in os.getenv("ALLOWED_IMAGE_TYPES", "image/jpeg,image/jpg,image/png").split(",")]
    
    # API 기본 URL (파일 업로드 URL 생성용)
    BE_API_URL: str = os.getenv("BE_API_URL", "http://localhost:8000")

    # bcrypt 비밀번호 해시 강도 (rounds, 기본 12권장, 높을수록 안전하나 느려짐)
    BCRYPT_ROUNDS: int = int(os.getenv("BCRYPT_ROUNDS", "12"))

    # DB (SQL 로깅·연결 확인용 SQLite 경로)
    DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite:///./puppytalk.db")

# 전역 설정 인스턴스
settings = Settings()
