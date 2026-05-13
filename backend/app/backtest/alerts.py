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
