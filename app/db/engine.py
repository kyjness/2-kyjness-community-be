# DB 엔진·SessionLocal. PostgreSQL(psycopg3). Full-Async. WRITER_DB_URL/READER_DB_URL 분리 시 Read/Write Splitting.
from urllib.parse import quote_plus

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import settings


def _default_db_url() -> str:
    return (
        f"postgresql+psycopg://{settings.DB_USER}:{quote_plus(settings.DB_PASSWORD)}"
        f"@{settings.DB_HOST}:{settings.DB_PORT}/{settings.DB_NAME}"
    )


def _make_async_engine(url: str) -> AsyncEngine:
    return create_async_engine(
        url,
        # echo=True,
        pool_size=settings.DB_POOL_SIZE,
        max_overflow=settings.DB_MAX_OVERFLOW,
        pool_recycle=settings.DB_POOL_RECYCLE,
        pool_pre_ping=True,
        connect_args={"connect_timeout": settings.DB_PING_TIMEOUT},
    )


_writer_url = settings.WRITER_DB_URL or _default_db_url()
_reader_url = settings.READER_DB_URL or _writer_url

writer_engine: AsyncEngine = _make_async_engine(_writer_url)
reader_engine: AsyncEngine = _make_async_engine(_reader_url)

# autobegin=False: 트랜잭션은 서비스 레이어에서 async with db.begin()으로만 시작.
AsyncSessionLocal = async_sessionmaker(
    writer_engine,
    class_=AsyncSession,
    autocommit=False,
    autoflush=False,
    autobegin=False,
    expire_on_commit=False,
)
AsyncSessionLocalReader = async_sessionmaker(
    reader_engine,
    class_=AsyncSession,
    autocommit=False,
    autoflush=False,
    autobegin=False,
    expire_on_commit=False,
)

# 하위 호환
engine: AsyncEngine = writer_engine
