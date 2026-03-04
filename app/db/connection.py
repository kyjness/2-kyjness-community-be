# DB 연결 수명 주기. init_database, check_database(writer/reader 둘 다), close_database.
import logging

from sqlalchemy import text

from app.db.engine import writer_engine, reader_engine

logger = logging.getLogger(__name__)


def init_database() -> bool:
    return check_database()


def check_database() -> bool:
    try:
        with writer_engine.connect() as conn:
            conn.execute(text("SELECT 1")).fetchone()
        with reader_engine.connect() as conn:
            conn.execute(text("SELECT 1")).fetchone()
        return True
    except Exception as e:
        logger.error("MySQL 연결 실패: %s", e)
        return False


def close_database() -> None:
    writer_engine.dispose()
    reader_engine.dispose()
