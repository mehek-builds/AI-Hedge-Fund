"""Tests for FR-6.4 and FR-6.5: gate logic.

FR-6.4: gate fires backtest_gate_pass/backtest_gate_fail at end of replay.
FR-6.5: ex-2020 stress slice must have Sharpe > 0.8 for gate to pass.
"""

import sys
import os
from unittest.mock import MagicMock

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from app.backtest.gate import (
    evaluate_gate,
    GateResult,
    SHARPE_THRESHOLD,
    EX2020_SHARPE_THRESHOLD,
)
from app.backtest.alerts import fire_gate_alert


class TestGateEvaluation:
    """FR-6.4: programmatic go/no-go gate logic."""

    def test_gate_pass_when_sharpe_above_threshold(self):
        """Sharpe > 1.0 with no ex-2020 check should pass."""
        result = evaluate_gate(full_sharpe=1.2)
        assert result.gate_status == "pass"

    def test_gate_fail_when_sharpe_at_threshold(self):
        """Sharpe exactly at threshold (1.0) should fail (> not >=)."""
        result = evaluate_gate(full_sharpe=SHARPE_THRESHOLD)
        assert result.gate_status == "fail"

    def test_gate_fail_when_sharpe_below_threshold(self):
        """Sharpe < 1.0 must fail."""
        result = evaluate_gate(full_sharpe=0.9)
        assert result.gate_status == "fail"

    def test_gate_pass_with_ex2020_above_threshold(self):
        """Full Sharpe > 1.0 and ex-2020 Sharpe > 0.8 should pass."""
        result = evaluate_gate(full_sharpe=1.3, ex2020_sharpe=0.9)
        assert result.gate_status == "pass"

    def test_gate_fail_when_ex2020_sharpe_below_threshold(self):
        """FR-6.5: ex-2020 Sharpe <= 0.8 must fail the gate even if full Sharpe passes."""
        result = evaluate_gate(full_sharpe=1.5, ex2020_sharpe=0.7)
        assert result.gate_status == "fail"

    def test_gate_fail_when_ex2020_sharpe_at_threshold(self):
        """ex-2020 Sharpe exactly at 0.8 should fail (> not >=)."""
        result = evaluate_gate(full_sharpe=1.5, ex2020_sharpe=EX2020_SHARPE_THRESHOLD)
        assert result.gate_status == "fail"

    def test_gate_pending_for_partial_year_slice(self):
        """Partial-year slices should not be gated (gate_status = 'pending')."""
        result = evaluate_gate(full_sharpe=0.5, is_partial_year=True)
        assert result.gate_status == "pending"

    def test_gate_override_forces_pass(self):
        """override_gate_pass=True must force pass regardless of Sharpe."""
        result = evaluate_gate(full_sharpe=0.2, override_gate_pass=True)
        assert result.gate_status == "pass"

    def test_gate_result_contains_sharpe_values(self):
        """GateResult must expose full_sharpe and ex2020_sharpe for audit."""
        result = evaluate_gate(full_sharpe=1.1, ex2020_sharpe=0.85)
        assert result.full_sharpe == pytest.approx(1.1)
        assert result.ex2020_sharpe == pytest.approx(0.85)

    def test_gate_result_contains_reason_string(self):
        """GateResult must include a reason string for logging and audit."""
        result = evaluate_gate(full_sharpe=1.2)
        assert isinstance(result.reason, str)
        assert len(result.reason) > 0


class TestEx2020Slice:
    """FR-6.5: ex-2020 stress slice specific tests."""

    def test_ex2020_slice_separately_evaluated(self):
        """ex-2020 slice is a separate gate condition, not a replacement."""
        # Full pass, ex-2020 fail -> overall fail
        result = evaluate_gate(full_sharpe=1.8, ex2020_sharpe=0.79)
        assert result.gate_status == "fail", (
            "ex-2020 slice must be an independent gate condition (FR-6.5)"
        )

    def test_ex2020_slice_none_does_not_fail(self):
        """If no ex-2020 slice provided, gate should not fail on that condition."""
        result = evaluate_gate(full_sharpe=1.2, ex2020_sharpe=None)
        assert result.gate_status == "pass"


class TestFireGateAlert:
    """FR-6.4: fire_gate_alert must update backtest_runs gate_status."""

    def test_fire_gate_alert_pass(self):
        """Gate pass alert must update backtest_runs to gate_status='pass'."""
        session = MagicMock()
        gate_result = GateResult(
            gate_status="pass",
            reason="sharpe=1.2 > 1.0",
            full_sharpe=1.2,
            ex2020_sharpe=None,
        )
        fire_gate_alert(session, gate_result, run_id="test-run-123")
        assert session.execute.called

    def test_fire_gate_alert_fail(self):
        """Gate fail alert must update backtest_runs to gate_status='fail'."""
        session = MagicMock()
        gate_result = GateResult(
            gate_status="fail",
            reason="sharpe=0.8 <= 1.0",
            full_sharpe=0.8,
            ex2020_sharpe=None,
        )
        fire_gate_alert(session, gate_result, run_id="test-run-456")
        assert session.execute.called

        # Verify the SQL updates gate_status
        call_args = session.execute.call_args
        params = call_args[0][1] if len(call_args[0]) > 1 else call_args[1]
        assert params.get("gate_status") == "fail"
