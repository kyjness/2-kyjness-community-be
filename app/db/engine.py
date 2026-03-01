# DB 엔진·SessionLocal 생성. config 기반 DATABASE_URL, pool 설정.
from urllib.parse import quote_plus

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import sessionmaker

from app.core.config import settings

DATABASE_URL = (
    f"mysql+pymysql://{settings.DB_USER}:{quote_plus(settings.DB_PASSWORD)}"
    f"@{settings.DB_HOST}:{settings.DB_PORT}/{settings.DB_NAME}"
    "?charset=utf8mb4"
)

engine: Engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,
    pool_recycle=3600,
    connect_args={"connect_timeout": settings.DB_PING_TIMEOUT},
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
