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


# ---------------------------------------------------------------------------
# Plan 06-03 gate tests: new dict-based API
# ---------------------------------------------------------------------------

from app.backtest.gate import (  # noqa: E402
    MAIN_SHARPE_THRESHOLD,
    EX2020_SHARPE_THRESHOLD,
    evaluate_gate_v2,
)
from app.backtest.alerts import (  # noqa: E402
    EVENT_TYPE_PASS,
    EVENT_TYPE_FAIL,
    fire_gate_alert_v2,
)


def _run(sharpe: float, is_partial_year: bool = False) -> dict:
    return {"sharpe": sharpe, "is_partial_year": is_partial_year}


def test_gate_conjunctive_pass():
    r = evaluate_gate_v2(_run(1.5), _run(0.9))
    assert r["gate_status"] == "pass", r


def test_gate_fails_when_main_below_threshold():
    r = evaluate_gate_v2(_run(0.99), _run(1.0))
    assert r["gate_status"] == "fail"
    assert "main slice" in r["gate_reason"]


def test_gate_fails_when_ex2020_below_threshold():
    """Critical case from CONTEXT.md: main passes but ex-2020 fails -> overall fail."""
    r = evaluate_gate_v2(_run(1.5), _run(0.79))
    assert r["gate_status"] == "fail"
    assert "ex-2020" in r["gate_reason"]


def test_gate_fails_when_both_below_threshold():
    r = evaluate_gate_v2(_run(0.5), _run(0.5))
    assert r["gate_status"] == "fail"
    assert "main slice" in r["gate_reason"] and "ex-2020" in r["gate_reason"]


def test_gate_pending_on_partial_year():
    r = evaluate_gate_v2(_run(1.5, is_partial_year=True), _run(0.9))
    assert r["gate_status"] == "pending"


def test_gate_override_forces_pass():
    """Even with a genuine fail, override=True returns pass."""
    r = evaluate_gate_v2(_run(0.5), _run(0.5), override=True)
    assert r["gate_status"] == "pass"
    assert "override" in r["gate_reason"]


def test_gate_thresholds_are_exact():
    """Boundary: exactly at threshold passes (>= comparison)."""
    r = evaluate_gate_v2(_run(MAIN_SHARPE_THRESHOLD), _run(EX2020_SHARPE_THRESHOLD))
    assert r["gate_status"] == "pass"


def test_fire_gate_alert_v2_pass_event_type():
    e = fire_gate_alert_v2("pass", "all good", run_id="abc-123")
    assert e["event_type"] == EVENT_TYPE_PASS
    assert e["run_id"] == "abc-123"
    assert e["reason"] == "all good"


def test_fire_gate_alert_v2_fail_event_type():
    e = fire_gate_alert_v2("fail", "main slice failed", run_id=None)
    assert e["event_type"] == EVENT_TYPE_FAIL
    assert e["run_id"] is None


def test_ex2020_slice():
    """FR-6.5: ex-2020 slice is reported as separate run; gate evaluates both."""
    main = _run(1.2)
    ex2020 = _run(0.85)
    r = evaluate_gate_v2(main, ex2020)
    assert r["gate_status"] == "pass"
    assert "1.2" in r["gate_reason"] or "1.200" in r["gate_reason"]
    assert "0.85" in r["gate_reason"] or "0.8500" in r["gate_reason"]
