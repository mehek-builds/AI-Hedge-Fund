"""Earnings monitor Prefect flow — polls every 15 min during market hours.

Detects new announcements from FMP and triggers compute_signal tasks.
"""

from __future__ import annotations

import os
from datetime import datetime, time as dt_time, timezone

from loguru import logger
from prefect import flow, task

FMP_API_KEY = os.environ.get("FMP_API_KEY", "")
DATABASE_URL_SYNC = os.environ.get(
    "DATABASE_URL_SYNC",
    "postgresql+psycopg2://postgres:postgres@db:5432/pead",
)

# Market hours in ET: 9:30 AM – 4:00 PM
_MARKET_OPEN = dt_time(9, 30)
_MARKET_CLOSE = dt_time(16, 0)


def _is_market_hours() -> bool:
    """Return True if current ET time is within regular market hours."""
    import zoneinfo

    try:
        tz = zoneinfo.ZoneInfo("America/New_York")
    except Exception:
        return True  # Assume open if timezone unavailable

    now_et = datetime.now(tz).time()
    return _MARKET_OPEN <= now_et <= _MARKET_CLOSE


@task(name="fetch_fmp_earnings_task", retries=2, retry_delay_seconds=60)
def fetch_fmp_earnings() -> list[dict]:
    """Fetch today's earnings announcements from FMP."""
    import requests

    if not FMP_API_KEY:
        logger.warning("FMP_API_KEY not set — skipping earnings fetch")
        return []

    today = datetime.now(timezone.utc).date()
    url = (
        f"https://financialmodelingprep.com/api/v3/earning_calendar"
        f"?from={today}&to={today}&apikey={FMP_API_KEY}"
    )

    try:
        resp = requests.get(url, timeout=30)
        resp.raise_for_status()
        return resp.json() or []
    except Exception as exc:
        logger.error(f"FMP fetch failed: {exc}")
        return []


@task(name="detect_new_announcements_task")
def detect_new_announcements(fmp_events: list[dict]) -> list[str]:
    """
    Compare FMP events against existing earnings_events in DB.
    For events with actual EPS that aren't yet in the DB (or lack a signal),
    upsert them and return their IDs to trigger compute_signal.
    """
    if not fmp_events:
        return []

    from sqlalchemy import create_engine, text

    engine = create_engine(DATABASE_URL_SYNC, pool_pre_ping=True)

    trigger_ids: list[str] = []

    with engine.begin() as conn:
        for event in fmp_events:
            ticker = event.get("symbol")
            date_str = event.get("date")
            eps_actual = event.get("eps")
            eps_est = event.get("epsEstimated")

            if not ticker or not date_str:
                continue

            # Only process events that have actual EPS reported
            if eps_actual is None:
                continue

            try:
                announcement_ts = datetime.fromisoformat(date_str)
            except ValueError:
                try:
                    announcement_ts = datetime.strptime(date_str, "%Y-%m-%d")
                except ValueError:
                    continue

            # Check if event already processed (has signal_composite)
            existing = conn.execute(
                text(
                    """
                    SELECT id, signal_composite FROM earnings_events
                    WHERE ticker = :ticker
                      AND announcement_ts::date = :date
                    """
                ),
                {"ticker": ticker.upper(), "date": announcement_ts.date()},
            ).fetchone()

            if existing and existing[1] is not None:
                # Already has a signal — skip
                continue

            if existing:
                event_id = str(existing[0])
                # Update with latest EPS data
                conn.execute(
                    text(
                        """
                        UPDATE earnings_events SET actual_eps = :actual_eps, consensus_eps = :consensus_eps
                        WHERE id = :id
                        """
                    ),
                    {"actual_eps": float(eps_actual), "consensus_eps": float(eps_est or 0), "id": event_id},
                )
            else:
                # Insert new event
                result = conn.execute(
                    text(
                        """
                        INSERT INTO earnings_events
                            (ticker, announcement_ts, actual_eps, consensus_eps)
                        VALUES (:ticker, :announcement_ts, :actual_eps, :consensus_eps)
                        RETURNING id
                        """
                    ),
                    {
                        "ticker": ticker.upper(),
                        "announcement_ts": announcement_ts,
                        "actual_eps": float(eps_actual),
                        "consensus_eps": float(eps_est or 0),
                    },
                ).fetchone()
                event_id = str(result[0])

            trigger_ids.append(event_id)
            logger.info(f"New announcement detected: {ticker} — queuing compute_signal({event_id})")

    return trigger_ids


@task(name="trigger_signal_tasks")
def trigger_signal_tasks(event_ids: list[str]) -> int:
    """Dispatch compute_signal Celery tasks for each new announcement."""
    if not event_ids:
        return 0

    from worker.tasks.signal import compute_signal

    for event_id in event_ids:
        compute_signal.delay(event_id)

    logger.info(f"Triggered compute_signal for {len(event_ids)} events")
    return len(event_ids)


@flow(
    name="earnings_monitor_flow",
    description="Polls FMP every 15 min during market hours for new earnings announcements",
)
def earnings_monitor_flow() -> None:
    """Poll FMP for new earnings and trigger signal computation tasks."""
    if not _is_market_hours():
        logger.debug("Outside market hours — skipping earnings monitor")
        return

    logger.info(f"earnings_monitor_flow starting at {datetime.now(timezone.utc)}")

    fmp_events = fetch_fmp_earnings()
    new_event_ids = detect_new_announcements(fmp_events)
    triggered = trigger_signal_tasks(new_event_ids)

    logger.info(f"earnings_monitor_flow complete: {triggered} signals triggered")


if __name__ == "__main__":
    earnings_monitor_flow()
