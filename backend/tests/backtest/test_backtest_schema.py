"""Tests for FR-6.6: backtest_runs schema has all required columns.

Validates the ORM model definition (not the live DB schema) to catch
column omissions at code-review time rather than at runtime.
"""

import sys
import os


sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from app.models.backtest_runs import BacktestRun


class TestBacktestRunsSchema:
    """Verify BacktestRun ORM model has all Phase 8 Explorer required columns."""

    REQUIRED_COLUMNS = [
        "id",
        "start_date",
        "end_date",
        "sharpe",
        "max_drawdown",
        "ir_vs_baseline",
        "calmar",
        "monthly_returns",
        "gate_status",
        "is_partial_year",
        "config_snapshot",
        "created_at",
    ]

    def test_all_required_columns_present(self):
        """BacktestRun must have all columns required by Phase 8 Backtest Explorer."""
        column_names = {c.key for c in BacktestRun.__table__.columns}
        for col in self.REQUIRED_COLUMNS:
            assert col in column_names, (
                f"BacktestRun missing required column: '{col}' (FR-6.6)"
            )

    def test_gate_status_check_constraint_exists(self):
        """gate_status must have a CHECK constraint to prevent invalid values."""
        constraints = BacktestRun.__table__.constraints
        # At least one constraint referencing 'gate_status' must exist
        assert any("gate_status" in str(c) for c in constraints), (
            "gate_status must have a CHECK constraint (pending/pass/fail)"
        )

    def test_table_name_is_backtest_runs(self):
        """ORM model must map to 'backtest_runs' table."""
        assert BacktestRun.__tablename__ == "backtest_runs"

    def test_monthly_returns_is_jsonb_type(self):
        """monthly_returns must be JSONB (not TEXT) for Phase 8 Explorer queries."""
        from sqlalchemy.dialects.postgresql import JSONB

        col = BacktestRun.__table__.columns["monthly_returns"]
        assert isinstance(col.type, JSONB), (
            "monthly_returns must be JSONB for Phase 8 Explorer queries"
        )

    def test_config_snapshot_is_jsonb_type(self):
        """config_snapshot must be JSONB for Phase 8 Explorer queries."""
        from sqlalchemy.dialects.postgresql import JSONB

        col = BacktestRun.__table__.columns["config_snapshot"]
        assert isinstance(col.type, JSONB), "config_snapshot must be JSONB"

    def test_id_is_uuid_type(self):
        """id column must be UUID type."""
        from sqlalchemy.dialects.postgresql import UUID

        col = BacktestRun.__table__.columns["id"]
        assert isinstance(col.type, UUID), "id must be UUID type"
