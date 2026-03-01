# DB 연결 수명 주기. init_database, check_database, close_database.
import logging

from sqlalchemy import text

from app.db.engine import engine

logger = logging.getLogger(__name__)


def init_database() -> bool:
    return check_database()


def check_database() -> bool:
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1")).fetchone()
        return True
    except Exception as e:
        logger.error("MySQL 연결 실패: %s", e)
        return False


def close_database() -> None:
    engine.dispose()
