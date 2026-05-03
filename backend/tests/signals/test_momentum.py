"""Tests for momentum.py — 20-day return and cohort percentile ranking."""
from datetime import datetime, timezone
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import MagicMock, call

import pytest


# ---------------------------------------------------------------------------
# twenty_day_return — DB-mocked tests
# ---------------------------------------------------------------------------

def _make_session(rows):
    """Return a MagicMock session whose execute().fetchall() returns `rows`."""
    session = MagicMock()
    session.execute.return_value.fetchall.return_value = rows
    return session


class TestTwentyDayReturn:
    def test_returns_none_when_fewer_than_21_rows(self):
        from app.signals.momentum import twenty_day_return

        session = _make_session([(Decimal("100"),)] * 20)  # only 20 rows
        result = twenty_day_return(session, "AAPL", datetime(2024, 1, 31, tzinfo=timezone.utc))
        assert result is None

    def test_returns_none_when_zero_rows(self):
        from app.signals.momentum import twenty_day_return

        session = _make_session([])
        result = twenty_day_return(session, "AAPL", datetime(2024, 1, 31, tzinfo=timezone.utc))
        assert result is None

    def test_returns_none_when_twenty_back_close_is_zero(self):
        from app.signals.momentum import twenty_day_return

        # 21 rows: today = 110, 20 back = 0
        rows = [(Decimal("110"),)] + [(Decimal("100"),)] * 19 + [(Decimal("0"),)]
        session = _make_session(rows)
        result = twenty_day_return(session, "AAPL", datetime(2024, 1, 31, tzinfo=timezone.utc))
        assert result is None

    def test_returns_none_when_today_close_is_none(self):
        from app.signals.momentum import twenty_day_return

        rows = [(None,)] + [(Decimal("100"),)] * 20
        session = _make_session(rows)
        result = twenty_day_return(session, "AAPL", datetime(2024, 1, 31, tzinfo=timezone.utc))
        assert result is None

    def test_correct_return_calculated(self):
        from app.signals.momentum import twenty_day_return

        # 21 rows DESC: today=110, last=100 → return = (110-100)/100 = 0.10
        rows = [(Decimal("110"),)] + [(Decimal("105"),)] * 19 + [(Decimal("100"),)]
        session = _make_session(rows)
        result = twenty_day_return(session, "AAPL", datetime(2024, 1, 31, tzinfo=timezone.utc))
        assert result == pytest.approx(0.10)

    def test_sql_contains_ingestion_timestamp_filter(self):
        """SQL must include point-in-time guard ingestion_timestamp <= :as_of."""
        from app.signals import momentum as momentum_module
        import inspect
        src = inspect.getsource(momentum_module.twenty_day_return)
        assert "ingestion_timestamp <= :as_of" in src

    def test_sql_contains_limit_21(self):
        """SQL must use LIMIT 21."""
        from app.signals import momentum as momentum_module
        import inspect
        src = inspect.getsource(momentum_module.twenty_day_return)
        assert "LIMIT 21" in src


# ---------------------------------------------------------------------------
# compute_momentum_score — pure percentile rank tests
# ---------------------------------------------------------------------------

class TestComputeMomentumScore:
    def test_none_symbol_return_gives_50(self):
        from app.signals.momentum import compute_momentum_score
        assert compute_momentum_score(None, [0.1, 0.2, 0.3]) == Decimal("50.0")

    def test_empty_cohort_gives_50(self):
        from app.signals.momentum import compute_momentum_score
        assert compute_momentum_score(0.15, []) == Decimal("50.0")

    def test_none_and_empty_gives_50(self):
        from app.signals.momentum import compute_momentum_score
        assert compute_momentum_score(None, []) == Decimal("50.0")

    def test_max_return_gives_100(self):
        from app.signals.momentum import compute_momentum_score
        cohort = [0.01, 0.05, 0.10]
        result = compute_momentum_score(0.10, cohort)
        assert result == Decimal("100.0")

    def test_min_return_gives_0(self):
        from app.signals.momentum import compute_momentum_score
        cohort = [0.01, 0.05, 0.10]
        result = compute_momentum_score(0.01, cohort)
        assert result == Decimal("0.0")

    def test_median_of_odd_cohort_gives_50_approx(self):
        from app.signals.momentum import compute_momentum_score
        cohort = [0.01, 0.03, 0.05, 0.07, 0.09]
        result = compute_momentum_score(0.05, cohort)
        # Median element → approx 50 (within 0.01 tolerance per plan)
        assert abs(float(result) - 50.0) < 0.01

    def test_single_element_cohort_tied_gives_50(self):
        from app.signals.momentum import compute_momentum_score
        result = compute_momentum_score(0.05, [0.05])
        assert result == Decimal("50.0")

    def test_five_element_cohort_tied_middle(self):
        from app.signals.momentum import compute_momentum_score
        cohort = [0.01, 0.03, 0.05, 0.07, 0.09]
        # symbol_return tied with cohort[2] (0.05)
        result = compute_momentum_score(0.05, cohort)
        assert abs(float(result) - 50.0) < 0.01

    def test_result_is_decimal(self):
        from app.signals.momentum import compute_momentum_score
        result = compute_momentum_score(0.05, [0.03, 0.05, 0.07])
        assert isinstance(result, Decimal)

    def test_below_all_cohort_returns_0(self):
        from app.signals.momentum import compute_momentum_score
        cohort = [0.05, 0.10, 0.15]
        result = compute_momentum_score(-0.10, cohort)
        assert result == Decimal("0.0")

    def test_above_all_cohort_returns_100(self):
        from app.signals.momentum import compute_momentum_score
        cohort = [0.05, 0.10, 0.15]
        result = compute_momentum_score(0.20, cohort)
        assert result == Decimal("100.0")
