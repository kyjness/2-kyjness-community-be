# DB 연결 수명 주기. init_database(시작 시 재시도), check_database, close_database. 비동기.
import asyncio
import logging

from sqlalchemy import text

from app.core.config import settings
from app.db.engine import reader_engine, writer_engine

logger = logging.getLogger(__name__)


async def _try_connect() -> tuple[bool, Exception | None]:
    try:
        async with writer_engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        async with reader_engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        return True, None
    except Exception as e:
        return False, e


async def check_database() -> bool:
    ok, err = await _try_connect()
    if not ok and err is not None:
        logger.error("PostgreSQL 연결 실패: %s", err)
    return ok


async def init_database() -> bool:
    max_attempts = settings.DB_INIT_MAX_ATTEMPTS
    delay = max(0.0, settings.DB_INIT_RETRY_DELAY_SECONDS)
    last_err: Exception | None = None
    for attempt in range(1, max_attempts + 1):
        ok, err = await _try_connect()
        if ok:
            return True
        last_err = err
        if attempt < max_attempts:
            logger.warning(
                "PostgreSQL 연결 실패 (%s/%s): %s — %.1fs 후 재시도",
                attempt,
                max_attempts,
                err,
                delay,
            )
            if delay > 0:
                await asyncio.sleep(delay)
    if last_err is not None:
        logger.error("PostgreSQL 연결 실패 (최종, %s회 시도): %s", max_attempts, last_err)
    return False


async def close_database() -> None:
    await writer_engine.dispose()
    await reader_engine.dispose()
