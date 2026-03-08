# DB 연결 수명 주기. init_database, check_database(writer/reader 둘 다), close_database. 비동기.
import logging

from sqlalchemy import text

from app.db.engine import reader_engine, writer_engine

logger = logging.getLogger(__name__)


async def check_database() -> bool:
    try:
        async with writer_engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        async with reader_engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        return True
    except Exception as e:
        logger.error("PostgreSQL 연결 실패: %s", e)
        return False


async def init_database() -> bool:
    return await check_database()


async def close_database() -> None:
    await writer_engine.dispose()
    await reader_engine.dispose()
