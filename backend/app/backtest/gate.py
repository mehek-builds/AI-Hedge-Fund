"""Programmatic go/no-go gate for backtest results.

FR-6.4: gate fires backtest_gate_pass or backtest_gate_fail.
FR-6.5: ex-2020 stress slice must report Sharpe > 0.8.

Gate conditions (conjunctive):
1. Full-period Sharpe ratio > 1.0
2. Ex-2020 slice Sharpe > 0.8 (if ex-2020 row is present)
3. is_partial_year = False for the main slice

The gate only runs on complete-year slices (is_partial_year = False).
"""

import logging
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger(__name__)

# Gate thresholds
SHARPE_THRESHOLD = 1.0
EX2020_SHARPE_THRESHOLD = 0.8


@dataclass
class GateResult:
    """Result of the programmatic go/no-go gate evaluation."""

    gate_status: str  # 'pass' or 'fail'
    reason: str
    full_sharpe: float
    ex2020_sharpe: Optional[float]


def evaluate_gate(
    full_sharpe: float,
    ex2020_sharpe: Optional[float] = None,
    is_partial_year: bool = False,
    override_gate_pass: bool = False,
) -> GateResult:
    """Evaluate the conjunctive go/no-go gate.

    Args:
        full_sharpe: Sharpe ratio of the full backtest run
        ex2020_sharpe: Sharpe of the ex-2020 stress slice (None if not computed)
        is_partial_year: if True, gate does not run (partial years are not gated)
        override_gate_pass: if True, force pass status (documented bypass only)

    Returns GateResult with gate_status 'pass' or 'fail'.
    """
    if override_gate_pass:
        logger.warning(
            "Gate override_gate_pass=True: forcing pass status (Sharpe=%.3f)",
            full_sharpe,
        )
        return GateResult(
            gate_status="pass",
            reason="override_gate_pass=True (manual override)",
            full_sharpe=full_sharpe,
            ex2020_sharpe=ex2020_sharpe,
        )

    if is_partial_year:
        logger.info(
            "Partial-year slice: gate not evaluated (Sharpe=%.3f)", full_sharpe
        )
        return GateResult(
            gate_status="pending",
            reason="partial_year: gate not applied to partial-year slices",
            full_sharpe=full_sharpe,
            ex2020_sharpe=ex2020_sharpe,
        )

    # Condition 1: full-period Sharpe > 1.0
    if full_sharpe <= SHARPE_THRESHOLD:
        reason = (
            f"full_period_sharpe={full_sharpe:.3f} <= threshold={SHARPE_THRESHOLD}"
        )
        logger.warning("Gate FAIL: %s", reason)
        return GateResult(
            gate_status="fail",
            reason=reason,
            full_sharpe=full_sharpe,
            ex2020_sharpe=ex2020_sharpe,
        )

    # Condition 2: ex-2020 Sharpe > 0.8 (if provided)
    if ex2020_sharpe is not None and ex2020_sharpe <= EX2020_SHARPE_THRESHOLD:
        reason = (
            f"ex2020_sharpe={ex2020_sharpe:.3f} <= threshold={EX2020_SHARPE_THRESHOLD}"
        )
        logger.warning("Gate FAIL: %s", reason)
        return GateResult(
            gate_status="fail",
            reason=reason,
            full_sharpe=full_sharpe,
            ex2020_sharpe=ex2020_sharpe,
        )

    reason = (
        f"full_sharpe={full_sharpe:.3f} > {SHARPE_THRESHOLD}"
        + (
            f", ex2020_sharpe={ex2020_sharpe:.3f} > {EX2020_SHARPE_THRESHOLD}"
            if ex2020_sharpe is not None
            else ""
        )
    )
    logger.info("Gate PASS: %s", reason)
    return GateResult(
        gate_status="pass",
        reason=reason,
        full_sharpe=full_sharpe,
        ex2020_sharpe=ex2020_sharpe,
    )
