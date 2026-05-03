import subprocess

import pytest
from sqlalchemy import text

EXPECTED_HYPERTABLES = {
    "price_bars",
    "earnings_events",
    "signals",
    "rl_transitions",
    "macro_indicators",
    "portfolio_positions",
}


@pytest.mark.asyncio
async def test_all_six_hypertables_exist(db):
    result = await db.execute(
        text("SELECT hypertable_name FROM timescaledb_information.hypertables")
    )
    found = {row[0] for row in result.fetchall()}
    assert EXPECTED_HYPERTABLES == found, (
        f"Missing hypertables: {EXPECTED_HYPERTABLES - found}, "
        f"unexpected: {found - EXPECTED_HYPERTABLES}"
    )


@pytest.mark.asyncio
async def test_ingestion_timestamp_columns(db):
    for table in EXPECTED_HYPERTABLES:
        result = await db.execute(
            text(
                "SELECT column_name, data_type, is_nullable "
                "FROM information_schema.columns "
                "WHERE table_schema = 'public' "
                "  AND table_name = :t "
                "  AND column_name = 'ingestion_timestamp'"
            ),
            {"t": table},
        )
        row = result.fetchone()
        assert row is not None, f"No ingestion_timestamp column on {table}"
        assert row[1] == "timestamp with time zone", (
            f"{table}.ingestion_timestamp has type {row[1]}"
        )
        assert row[2] == "NO", f"{table}.ingestion_timestamp allows NULL"


@pytest.mark.asyncio
async def test_hypertable_inserts(db):
    inserts = [
        (
            "price_bars",
            "INSERT INTO price_bars (time, symbol, close, ingestion_timestamp) "
            "VALUES (NOW() - INTERVAL '1 hour', 'TST', 100.00, NOW())",
        ),
        (
            "earnings_events",
            "INSERT INTO earnings_events "
            "(announced_at, symbol, fiscal_quarter, guidance_direction) "
            "VALUES (NOW() - INTERVAL '1 hour', 'TST', 'Q1-2024', 'none')",
        ),
        (
            "signals",
            "INSERT INTO signals (created_at, signal_id, direction) "
            "VALUES (NOW() - INTERVAL '1 hour', gen_random_uuid(), 'long')",
        ),
        (
            "rl_transitions",
            "INSERT INTO rl_transitions (ts, episode_id, step, agent_id) "
            "VALUES (NOW() - INTERVAL '1 hour', gen_random_uuid(), 0, 0)",
        ),
        (
            "macro_indicators",
            "INSERT INTO macro_indicators (date, series_id, value) "
            "VALUES (CURRENT_DATE - 1, 'TEST_SERIES', 1.23)",
        ),
        (
            "portfolio_positions",
            "INSERT INTO portfolio_positions (snapshot_at, symbol, qty) "
            "VALUES (NOW() - INTERVAL '1 hour', 'TST', 1.0000)",
        ),
    ]
    for table, stmt in inserts:
        await db.execute(text(stmt))
        result = await db.execute(
            text(f"SELECT count(*) FROM {table}")  # noqa: S608
        )
        count = result.scalar()
        assert count >= 1, f"Insert into {table} produced no rows"


@pytest.mark.asyncio
async def test_migration_idempotent(db_engine):
    """Running `alembic upgrade head` a second time must not raise."""
    import os

    env = {**os.environ, "DATABASE_URL": str(db_engine.url)}
    result = subprocess.run(
        ["alembic", "upgrade", "head"],
        cwd=str(db_engine.url).split("@")[-1] and _backend_dir(),
        capture_output=True,
        text=True,
        env=env,
    )
    assert result.returncode == 0, (
        f"alembic upgrade head failed:\n{result.stdout}\n{result.stderr}"
    )


def _backend_dir() -> str:
    import pathlib
    return str(pathlib.Path(__file__).parent.parent)
