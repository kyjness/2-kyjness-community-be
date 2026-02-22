# app/core/database.py
"""DB 연결 관리 (MySQL puppytalk). per-call 연결, 요청 후 close 보장."""

import logging
from contextlib import contextmanager

import pymysql
from pymysql.cursors import DictCursor

from app.core.config import settings

logger = logging.getLogger(__name__)


@contextmanager
def get_connection():
    """MySQL 연결 context manager. DictCursor로 dict 형태 행 반환. 사용 후 자동 close.
    여러 model 호출을 한 트랜잭션으로 묶을 때: with get_connection() as conn: ...; model.xxx(..., conn=conn); conn.commit()
    예외 시 자동 rollback."""
    conn = None
    try:
        conn = pymysql.connect(
            host=settings.DB_HOST,
            port=settings.DB_PORT,
            user=settings.DB_USER,
            password=settings.DB_PASSWORD,
            database=settings.DB_NAME,
            charset="utf8mb4",
            cursorclass=DictCursor,
            autocommit=False,
        )
        yield conn
    except Exception:
        if conn:
            try:
                conn.rollback()
            except Exception:
                pass
        raise
    finally:
        if conn:
            try:
                conn.close()
            except Exception:
                pass


def init_database() -> bool:
    """서버 시작 시 DB 연결 체크. SELECT 1 실행."""
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1")
        return True
    except Exception as e:
        logger.error("MySQL 연결 실패: %s", e)
        return False


def close_database() -> None:
    """연결 종료. per-call 연결 사용 시 no-op."""
    pass
