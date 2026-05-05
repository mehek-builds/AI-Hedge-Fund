import asyncio
import os

import httpx
import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from app.main import app

DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql+asyncpg://pead:devpass@localhost:5432/pead_trading",
)

_DB_AVAILABLE = bool(os.environ.get("DATABASE_URL") or os.environ.get("DATABASE_URL_SYNC"))

requires_db = pytest.mark.skipif(
    not _DB_AVAILABLE,
    reason="DB-gated: set DATABASE_URL or DATABASE_URL_SYNC and run `alembic upgrade head` first",
)


@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture(scope="session")
async def db_engine():
    if not _DB_AVAILABLE:
        pytest.skip("DB-gated: set DATABASE_URL or DATABASE_URL_SYNC first")
    engine = create_async_engine(DATABASE_URL, echo=False)
    try:
        async with engine.connect():
            pass
    except Exception:
        await engine.dispose()
        pytest.skip("PostgreSQL not reachable — skipping DB-dependent tests")
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture
async def db(db_engine):
    async_session = sessionmaker(
        db_engine, class_=AsyncSession, expire_on_commit=False
    )
    async with async_session() as session:
        yield session
        await session.rollback()


@pytest_asyncio.fixture
async def client():
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


@pytest_asyncio.fixture
async def db_session(db_engine):
    """Per-test async session for point-in-time query tests."""
    async_session = sessionmaker(
        db_engine, class_=AsyncSession, expire_on_commit=False
    )
    async with async_session() as session:
        yield session
        await session.rollback()
