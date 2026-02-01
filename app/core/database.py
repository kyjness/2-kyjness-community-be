# app/core/database.py
"""DB 연결 관리 (MySQL puupytalkdb)"""

from datetime import datetime

import pymysql
from pymysql.cursors import DictCursor

from app.core.config import settings

_connection = None


def get_connection():
    """MySQL 연결 반환 (DictCursor로 dict 형태 행 반환)"""
    global _connection
    if _connection is not None:
        return _connection

    _connection = pymysql.connect(
        host=settings.DB_HOST,
        port=settings.DB_PORT,
        user=settings.DB_USER,
        password=settings.DB_PASSWORD,
        database=settings.DB_NAME,
        charset="utf8mb4",
        cursorclass=DictCursor,
        autocommit=False,
    )
    return _connection


def init_database() -> bool:
    """DB 연결 및 확인"""
    try:
        conn = get_connection()
        with conn.cursor() as cur:
            cur.execute("SELECT 1")
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print(f"[{ts}] MySQL 연결 성공 ({settings.DB_NAME})", flush=True)
        return True
    except Exception as e:
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print(f"[{ts}] MySQL 연결 실패: {e}", flush=True)
        return False


def close_database() -> None:
    """연결 종료"""
    global _connection
    if _connection is not None:
        try:
            _connection.close()
        except Exception:
            pass
        _connection = None
