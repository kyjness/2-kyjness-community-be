# 비요청 스코프용 세션. get_connection(cleanup/exception 등). 요청 스코프용 get_master_db/get_slave_db는 app.api.dependencies.db.
from contextlib import asynccontextmanager

from app.db.engine import AsyncSessionLocal


@asynccontextmanager
async def get_connection():
    """cleanup·exception_handlers 등 비요청 스코프용. 호출부(서비스)에서 async with db.begin()으로 트랜잭션 관리."""
    async with AsyncSessionLocal() as db:
        try:
            yield db
        finally:
            await db.close()
