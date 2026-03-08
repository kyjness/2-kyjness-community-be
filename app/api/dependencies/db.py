# DB 세션 의존성. get_master_db(CUD) / get_slave_db(Read). 비동기 AsyncSession. 트랜잭션은 서비스 레이어에서 async with db.begin()으로 관리.
from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.engine import AsyncSessionLocal, AsyncSessionLocalReader


async def get_master_db() -> AsyncGenerator[AsyncSession, None]:
    """CUD용 Writer 세션. yield 후 close만 수행. commit/rollback은 서비스에서 async with db.begin()으로 처리."""
    async with AsyncSessionLocal() as db:
        try:
            yield db
        finally:
            await db.close()


async def get_slave_db() -> AsyncGenerator[AsyncSession, None]:
    """조회용 Reader 세션(READ ONLY). yield 후 close만 수행."""
    async with AsyncSessionLocalReader() as db:
        try:
            yield db
        finally:
            await db.close()
