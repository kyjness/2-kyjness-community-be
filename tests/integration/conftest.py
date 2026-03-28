import os
from collections.abc import AsyncIterator

import pytest
import pytest_asyncio
from app.api.dependencies import get_master_db, get_slave_db
from app.core.config import settings
from app.db.base import Base
from app.main import app
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.engine.url import make_url
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

TEST_DB_URL = os.getenv(
    "TEST_DB_URL",
    "postgresql+psycopg://postgres:0730@127.0.0.1:5432/puppytalk_test",
)


@pytest.fixture(scope="session", autouse=True)
def relax_integration_rate_limits() -> None:
    """동일 ASGI client IP로 연속 로그인 시 Redis 로그인 RL(기본 5회/창)에 걸린다. 통합 테스트만 상한 완화."""
    settings.LOGIN_RATE_LIMIT_MAX_ATTEMPTS = max(settings.LOGIN_RATE_LIMIT_MAX_ATTEMPTS, 10_000)


try:
    make_url(TEST_DB_URL)
except Exception as e:
    raise RuntimeError(
        f"유효하지 않은 TEST_DB_URL입니다: {TEST_DB_URL!r}. 환경 변수를 확인하세요."
    ) from e

test_engine = create_async_engine(TEST_DB_URL, echo=False)
TestSessionLocal = async_sessionmaker(
    test_engine, class_=AsyncSession, expire_on_commit=False, autobegin=True
)


@pytest_asyncio.fixture(scope="session", autouse=True)
async def setup_test_db(relax_integration_rate_limits):
    async with test_engine.begin() as conn:
        await conn.execute(text("DROP SCHEMA IF EXISTS public CASCADE"))
        await conn.execute(text("CREATE SCHEMA public"))
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS pg_trgm"))
        await conn.run_sync(Base.metadata.create_all)

    yield

    async with test_engine.begin() as conn:
        await conn.execute(text("DROP SCHEMA IF EXISTS public CASCADE"))
        await conn.execute(text("CREATE SCHEMA public"))


@pytest_asyncio.fixture
async def db_session() -> AsyncIterator[AsyncSession]:
    async with TestSessionLocal() as session:
        yield session


@pytest_asyncio.fixture
async def client(db_session: AsyncSession) -> AsyncIterator[AsyncClient]:
    # get_current_user 등은 get_slave_db(Reader)를 쓰므로 Writer만 오버라이드하면 401이 난다.
    async def override_test_db():
        yield db_session

    app.dependency_overrides[get_master_db] = override_test_db
    app.dependency_overrides[get_slave_db] = override_test_db

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac

    app.dependency_overrides.pop(get_master_db, None)
    app.dependency_overrides.pop(get_slave_db, None)
