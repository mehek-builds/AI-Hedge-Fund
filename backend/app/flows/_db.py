"""Synchronous SQLAlchemy engine for Prefect flows.

Uses postgresql+psycopg2 dialect (NOT asyncpg) because Prefect 2.x flows
are synchronous — the async engine cannot be used here.
DATABASE_URL_SYNC must be a postgresql+psycopg2:// URL.
"""

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.config import settings

sync_engine = create_engine(
    settings.DATABASE_URL_SYNC,  # postgresql+psycopg2://...
    pool_size=5,
    max_overflow=10,
    pool_pre_ping=True,
    future=True,
)

SyncSessionLocal = sessionmaker(sync_engine, expire_on_commit=False, future=True)
