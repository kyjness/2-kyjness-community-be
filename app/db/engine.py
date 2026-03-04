# DB 엔진·SessionLocal. WRITER_DB_URL/READER_DB_URL 분리 시 Read/Write Splitting. 미설정 시 _default_db_url() 사용.
from urllib.parse import quote_plus

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import sessionmaker

from app.core.config import settings


def _default_db_url() -> str:
    return (
        f"mysql+pymysql://{settings.DB_USER}:{quote_plus(settings.DB_PASSWORD)}"
        f"@{settings.DB_HOST}:{settings.DB_PORT}/{settings.DB_NAME}"
        "?charset=utf8mb4"
    )


def _set_mysql_utc(engine: Engine) -> None:
    @event.listens_for(engine, "connect")
    def _on_connect(dbapi_conn, connection_record):
        cursor = dbapi_conn.cursor()
        cursor.execute("SET SESSION time_zone = '+00:00'")
        cursor.close()


def _make_engine(url: str) -> Engine:
    eng = create_engine(
        url,
        pool_size=settings.DB_POOL_SIZE,
        max_overflow=settings.DB_MAX_OVERFLOW,
        pool_recycle=settings.DB_POOL_RECYCLE,
        pool_pre_ping=True,
        connect_args={"connect_timeout": settings.DB_PING_TIMEOUT},
    )
    _set_mysql_utc(eng)
    return eng


def _make_reader_engine(url: str) -> Engine:
    eng = create_engine(
        url,
        pool_size=settings.DB_POOL_SIZE,
        max_overflow=settings.DB_MAX_OVERFLOW,
        pool_recycle=settings.DB_POOL_RECYCLE,
        pool_pre_ping=True,
        connect_args={"connect_timeout": settings.DB_PING_TIMEOUT},
    )

    @event.listens_for(eng, "connect")
    def _on_connect(dbapi_conn, connection_record):
        cursor = dbapi_conn.cursor()
        cursor.execute("SET SESSION time_zone = '+00:00'")
        cursor.execute("SET SESSION TRANSACTION READ ONLY")
        cursor.close()

    return eng


_writer_url = settings.WRITER_DB_URL or _default_db_url()
_reader_url = settings.READER_DB_URL or _writer_url

writer_engine: Engine = _make_engine(_writer_url)
reader_engine: Engine = _make_reader_engine(_reader_url)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=writer_engine)
SessionLocalReader = sessionmaker(autocommit=False, autoflush=False, bind=reader_engine)

# 하위 호환: engine = writer
engine: Engine = writer_engine
