"""Backtest gate alert firing.

FR-6.4: fires backtest_gate_pass or backtest_gate_fail at end of replay.
Phase 7 startup reads gate_status from backtest_runs and refuses to start
when gate_status = 'fail'.

Alert types:
- backtest_gate_pass: Sharpe > 1.0 and ex-2020 Sharpe > 0.8
- backtest_gate_fail: gate conditions not met
"""

import logging
from datetime import datetime, timezone

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.backtest.gate import GateResult

logger = logging.getLogger(__name__)


def fire_gate_alert(
    session: Session,
    gate_result: GateResult,
    run_id: str,
) -> None:
    """Persist a gate alert to the database and log at the appropriate level.

    Writes to rl_diversity_alerts table is not appropriate here; this module
    logs the alert and updates the backtest_runs row via the caller. Actual
    persistence of gate_status happens in run_full_backtest via the ORM.

    Phase 7 startup gate check reads gate_status directly from backtest_runs.
    """
    alert_type = (
        "backtest_gate_pass"
        if gate_result.gate_status == "pass"
        else "backtest_gate_fail"
    )
    now = datetime.now(timezone.utc).isoformat()

    if gate_result.gate_status == "pass":
        logger.info(
            "[%s] run_id=%s at %s | reason: %s",
            alert_type,
            run_id,
            now,
            gate_result.reason,
        )
    else:
        logger.warning(
            "[%s] run_id=%s at %s | reason: %s",
            alert_type,
            run_id,
            now,
            gate_result.reason,
        )

    # Update gate_status in backtest_runs so Phase 7 can read it
    session.execute(
        text(
            """
            UPDATE backtest_runs
            SET gate_status = :gate_status
            WHERE id = :run_id
            """
        ),
        {"gate_status": gate_result.gate_status, "run_id": run_id},
    )


def check_phase7_gate(session: Session) -> bool:
    """Check if Phase 7 paper trading startup is permitted.

    Reads the most recent non-partial backtest_runs row. Returns True only if
    gate_status = 'pass'. Phase 7 startup must call this and abort on False.
    """
    row = session.execute(
        text(
            """
            SELECT gate_status
            FROM backtest_runs
            WHERE is_partial_year = FALSE
            ORDER BY created_at DESC
            LIMIT 1
            """
        )
    ).fetchone()

    if row is None:
        logger.error("Phase 7 gate check FAILED: no backtest_runs row found")
        return False

    if row[0] != "pass":
        logger.error(
            "Phase 7 gate check FAILED: most recent gate_status = '%s'", row[0]
        )
        return False

    logger.info("Phase 7 gate check PASSED: gate_status = 'pass'")
    return True


# ---------------------------------------------------------------------------
# Plan 06-03 stub interface for Phase 7 to wire to SendGrid+Slack
# ---------------------------------------------------------------------------

EVENT_TYPE_PASS = "backtest_gate_pass"
EVENT_TYPE_FAIL = "backtest_gate_fail"
EVENT_TYPE_PENDING = "backtest_gate_pending"


def fire_gate_alert_v2(gate_status: str, gate_reason: str, run_id) -> dict:
    """Return a structured alert event dict. Stub for now; Phase 7 wires this to SendGrid+Slack.

    gate_status: 'pass' | 'fail' | 'pending'
    Returns: {"event_type": str, "run_id": str|None, "reason": str}
    """
    if gate_status == "pass":
        event_type = EVENT_TYPE_PASS
    elif gate_status == "fail":
        event_type = EVENT_TYPE_FAIL
    else:
        event_type = EVENT_TYPE_PENDING
    event = {
        "event_type": event_type,
        "run_id": str(run_id) if run_id is not None else None,
        "reason": gate_reason,
    }
    logger.info("BACKTEST GATE EVENT: %s", event)

    # Phase 7: wire to real SendGrid+Slack delivery.
    # Called from sync Celery context (backtest runner); use asyncio.run().
    # Fire-and-forget: failure is logged, not raised.
    try:
        import asyncio as _asyncio
        import redis as _redis
        from app.alerting.dispatcher import dispatch_alert as _dispatch
        from app.config import settings as _settings
        from app.database import AsyncSessionLocal

        async def _deliver():
            r = _redis.from_url(_settings.REDIS_PUB_URL, decode_responses=True)
            async with AsyncSessionLocal() as async_session:
                await _dispatch(event["event_type"], event, async_session, r)

        _asyncio.run(_deliver())
    except Exception as _exc:
        logger.error("fire_gate_alert_v2 delivery failed (non-fatal): %s", _exc)

    return event
