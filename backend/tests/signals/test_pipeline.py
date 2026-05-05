"""Tests for pipeline.py — compute_signal_for_event end-to-end orchestration."""
import logging
from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import MagicMock, patch
import uuid



def _make_event(
    symbol="MSFT",
    announced_at=None,
    eps_actual=Decimal("2.50"),
    eps_estimate=Decimal("2.00"),
    revenue_actual=Decimal("50000"),
    revenue_estimate=Decimal("48000"),
    operating_income=Decimal("15000"),
    share_count=100_000_000,
    guidance_direction="up",
):
    if announced_at is None:
        announced_at = datetime(2024, 2, 1, tzinfo=timezone.utc)
    e = MagicMock()
    e.id = 1
    e.symbol = symbol
    e.announced_at = announced_at
    e.eps_actual = eps_actual
    e.eps_estimate = eps_estimate
    e.revenue_actual = revenue_actual
    e.revenue_estimate = revenue_estimate
    e.operating_income = operating_income
    e.share_count = share_count
    e.guidance_direction = guidance_direction
    return e


def _make_prior_event(
    revenue_actual=Decimal("45000"),
    revenue_estimate=Decimal("44000"),
    operating_income=Decimal("12000"),
    share_count=105_000_000,
    guidance_direction="flat",
    announced_at=None,
):
    if announced_at is None:
        announced_at = datetime(2023, 11, 1, tzinfo=timezone.utc)
    e = MagicMock()
    e.id = 0
    e.symbol = "MSFT"
    e.announced_at = announced_at
    e.revenue_actual = revenue_actual
    e.revenue_estimate = revenue_estimate
    e.operating_income = operating_income
    e.share_count = share_count
    e.guidance_direction = guidance_direction
    return e


# Sector for MSFT is "Tech" → hurdle=60, ROIC filter applies
# Sector for "XOM" is "Energy" → hurdle=45, ROIC filter NOT applicable


class TestComputeSignalForEvent:
    def _run_with_patches(
        self,
        session,
        event,
        prior_event=None,
        last_close=Decimal("300"),
        sym_return=0.05,
        cohort_eps_gaps=None,
        cohort_returns=None,
        write_signal_return="aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
    ):
        from app.signals import pipeline as pipe_module
        with (
            patch.object(pipe_module, "_load_event", return_value=event),
            patch.object(pipe_module, "_load_prior_event", return_value=prior_event),
            patch.object(pipe_module, "_last_close", return_value=last_close),
            patch.object(pipe_module, "twenty_day_return", return_value=sym_return),
            patch.object(pipe_module, "write_signal", return_value=write_signal_return) as mock_write,
        ):
            from app.signals.pipeline import compute_signal_for_event
            result = compute_signal_for_event(
                session,
                earnings_event_id=1,
                cohort_eps_gaps=cohort_eps_gaps or [],
                cohort_returns=cohort_returns or [],
            )
        return result, mock_write

    def test_happy_path_non_tech_returns_uuid(self):
        """Energy sector: no ROIC filter, quality hurdle=45. Should write signal."""
        session = MagicMock()
        event = _make_event(symbol="XOM")
        prior = _make_prior_event()
        # Quality: revenue_actual > rev_estimate → surprise ~11% → capped 25; margin: op income goes up; shares: 105M→100M buyback? no XOM prior has 105M shares
        result, mock_write = self._run_with_patches(session, event, prior_event=prior)
        assert result is not None
        # Should be a valid UUID
        uuid.UUID(result)
        mock_write.assert_called_once()

    def test_missing_event_returns_none(self):
        session = MagicMock()
        from app.signals import pipeline as pipe_module
        with (
            patch.object(pipe_module, "_load_event", return_value=None),
            patch.object(pipe_module, "write_signal") as mock_write,
        ):
            from app.signals.pipeline import compute_signal_for_event
            result = compute_signal_for_event(session, 999)
        assert result is None
        mock_write.assert_not_called()

    def test_missing_price_returns_none(self):
        session = MagicMock()
        event = _make_event(symbol="XOM")
        result, mock_write = self._run_with_patches(session, event, last_close=None)
        assert result is None
        mock_write.assert_not_called()

    def test_sector_hurdle_suppression_returns_none(self):
        """Tech symbol with quality_score < 60 → suppressed."""
        session = MagicMock()
        # MSFT is Tech, hurdle=60. Create event with no guidance/shares to get quality=0
        event = _make_event(
            symbol="MSFT",
            guidance_direction="none",  # 0 pts
            revenue_actual=Decimal("40000"),  # below estimate → 0 pts
            revenue_estimate=Decimal("48000"),
            operating_income=None,  # no margin component → 0 pts
            share_count=110_000_000,  # increased → 0 pts
        )
        prior = _make_prior_event(share_count=100_000_000)  # shares went up → 0 pts
        result, mock_write = self._run_with_patches(session, event, prior_event=prior)
        assert result is None
        mock_write.assert_not_called()

    def test_sector_hurdle_suppression_logs_warning(self, caplog):
        """Tech symbol with low quality → suppression logged at WARNING."""
        session = MagicMock()
        event = _make_event(
            symbol="MSFT",
            guidance_direction="none",
            revenue_actual=Decimal("40000"),
            revenue_estimate=Decimal("48000"),
            operating_income=None,
            share_count=110_000_000,
        )
        prior = _make_prior_event(share_count=100_000_000)
        with caplog.at_level(logging.WARNING, logger="app.signals.pipeline"):
            self._run_with_patches(session, event, prior_event=prior)
        assert any("hurdle" in rec.message.lower() or "suppressed" in rec.message.lower()
                   for rec in caplog.records)

    def test_roic_wacc_suppression_returns_none(self):
        """Tech symbol with quality>=60 but ROIC < 0.10 → suppressed."""
        session = MagicMock()
        # To get quality >= 60: need good revenue surprise + good guidance
        event = _make_event(
            symbol="MSFT",
            guidance_direction="up",        # 25 pts
            revenue_actual=Decimal("55000"),  # > estimate → beats by ~15% → capped 25 pts
            revenue_estimate=Decimal("48000"),
            operating_income=Decimal("200"),  # ROIC = 200 / (55000 * 0.4) = 0.009 < 0.10
            share_count=95_000_000,          # buyback → 25 pts
        )
        prior = _make_prior_event(
            share_count=100_000_000,
            operating_income=Decimal("12000"),
            revenue_actual=Decimal("48000"),
        )
        result, mock_write = self._run_with_patches(session, event, prior_event=prior)
        assert result is None
        mock_write.assert_not_called()

    def test_roic_wacc_suppression_logs_warning(self, caplog):
        session = MagicMock()
        event = _make_event(
            symbol="MSFT",
            guidance_direction="up",
            revenue_actual=Decimal("55000"),
            revenue_estimate=Decimal("48000"),
            operating_income=Decimal("200"),  # very low → ROIC < WACC
            share_count=95_000_000,
        )
        prior = _make_prior_event(share_count=100_000_000, operating_income=Decimal("12000"), revenue_actual=Decimal("48000"))
        with caplog.at_level(logging.WARNING, logger="app.signals.pipeline"):
            self._run_with_patches(session, event, prior_event=prior)
        assert any("ROIC" in rec.message or "suppressed" in rec.message.lower()
                   for rec in caplog.records)

    def test_naive_position_size_is_0_0200(self):
        """Position size persisted must be exactly 0.0200 regardless of composite."""
        session = MagicMock()
        event = _make_event(symbol="XOM")
        prior = _make_prior_event()
        captured_payloads = []
        from app.signals import pipeline as pipe_module
        with (
            patch.object(pipe_module, "_load_event", return_value=event),
            patch.object(pipe_module, "_load_prior_event", return_value=prior),
            patch.object(pipe_module, "_last_close", return_value=Decimal("300")),
            patch.object(pipe_module, "twenty_day_return", return_value=0.05),
            patch.object(pipe_module, "write_signal", side_effect=lambda s, p: captured_payloads.append(p) or "fake-uuid"),
        ):
            from app.signals.pipeline import compute_signal_for_event
            compute_signal_for_event(session, 1)
        assert len(captured_payloads) == 1
        assert captured_payloads[0].naive_position_size == Decimal("0.0200")

    def test_no_prior_event_proceeds(self):
        """compute_signal_for_event with prior=None should still proceed (quality handles it)."""
        session = MagicMock()
        event = _make_event(symbol="XOM")
        result, mock_write = self._run_with_patches(session, event, prior_event=None)
        # Energy with no prior: quality components without prior = 0 for margin/shares
        # Revenue surprise still counted; guidance=up=25 → total ~0-50 → depends on rev
        # Energy hurdle = 45 → may or may not write, but should NOT raise an exception
        assert result is None or isinstance(result, str)

    def test_write_signal_not_called_when_suppressed(self):
        """Ensure write_signal is never called for suppressed signals."""
        session = MagicMock()
        event = _make_event(
            symbol="MSFT",
            guidance_direction="none",
            revenue_actual=Decimal("40000"),
            revenue_estimate=Decimal("48000"),
            operating_income=None,
            share_count=110_000_000,
        )
        prior = _make_prior_event(share_count=100_000_000)
        from app.signals import pipeline as pipe_module
        with (
            patch.object(pipe_module, "_load_event", return_value=event),
            patch.object(pipe_module, "_load_prior_event", return_value=prior),
            patch.object(pipe_module, "_last_close", return_value=Decimal("300")),
            patch.object(pipe_module, "twenty_day_return", return_value=0.05),
            patch.object(pipe_module, "write_signal") as mock_write,
        ):
            from app.signals.pipeline import compute_signal_for_event
            result = compute_signal_for_event(session, 1)
        assert result is None
        mock_write.assert_not_called()
