"""Tests for writer.py — SignalPayload dataclass and write_signal function."""
from decimal import Decimal
from unittest.mock import MagicMock, patch
import uuid

import pytest


def _make_payload(**overrides):
    from app.signals.writer import SignalPayload, NAIVE_POSITION_SIZE
    defaults = dict(
        symbol="AAPL",
        earnings_event_id=42,
        eps_gap=Decimal("0.1500"),
        quality_score=Decimal("75"),
        three_axis_composite=Decimal("66.6667"),
        direction="long",
    )
    defaults.update(overrides)
    return SignalPayload(**defaults)


class TestSignalPayload:
    def test_default_naive_position_size_is_0_0200(self):
        from app.signals.writer import SignalPayload, NAIVE_POSITION_SIZE
        p = _make_payload()
        assert p.naive_position_size == Decimal("0.0200")

    def test_default_status_is_pending(self):
        p = _make_payload()
        assert p.status == "pending"

    def test_naive_position_size_constant(self):
        from app.signals.writer import NAIVE_POSITION_SIZE
        assert NAIVE_POSITION_SIZE == Decimal("0.0200")

    def test_payload_is_immutable(self):
        p = _make_payload()
        with pytest.raises((AttributeError, TypeError)):
            p.symbol = "MSFT"  # type: ignore[misc]


class TestWriteSignal:
    def test_returns_valid_uuid_string(self):
        from app.signals.writer import write_signal
        session = MagicMock()
        payload = _make_payload()
        result = write_signal(session, payload)
        # Should not raise
        parsed = uuid.UUID(result)
        assert str(parsed) == result

    def test_calls_upsert_rows_once(self):
        from app.signals.writer import write_signal
        session = MagicMock()
        payload = _make_payload()
        with patch("app.signals.writer.upsert_rows") as mock_upsert:
            write_signal(session, payload)
        mock_upsert.assert_called_once()

    def test_row_contains_naive_position_size_0_0200(self):
        from app.signals.writer import write_signal
        session = MagicMock()
        payload = _make_payload()
        captured_rows = []
        with patch("app.signals.writer.upsert_rows") as mock_upsert:
            mock_upsert.side_effect = lambda sess, table, rows, **kw: captured_rows.extend(rows)
            write_signal(session, payload)
        assert len(captured_rows) == 1
        assert captured_rows[0]["naive_position_size"] == Decimal("0.0200")

    def test_row_contains_status_pending(self):
        from app.signals.writer import write_signal
        session = MagicMock()
        payload = _make_payload()
        captured_rows = []
        with patch("app.signals.writer.upsert_rows") as mock_upsert:
            mock_upsert.side_effect = lambda sess, table, rows, **kw: captured_rows.extend(rows)
            write_signal(session, payload)
        assert captured_rows[0]["status"] == "pending"

    def test_row_contains_all_7_signal_columns(self):
        from app.signals.writer import write_signal
        session = MagicMock()
        payload = _make_payload()
        captured_rows = []
        with patch("app.signals.writer.upsert_rows") as mock_upsert:
            mock_upsert.side_effect = lambda sess, table, rows, **kw: captured_rows.extend(rows)
            write_signal(session, payload)
        row = captured_rows[0]
        for col in ("symbol", "earnings_event_id", "eps_gap", "quality_score",
                    "three_axis_composite", "naive_position_size", "direction"):
            assert col in row, f"Missing column: {col}"

    def test_row_symbol_matches_payload(self):
        from app.signals.writer import write_signal
        session = MagicMock()
        payload = _make_payload(symbol="NVDA")
        captured_rows = []
        with patch("app.signals.writer.upsert_rows") as mock_upsert:
            mock_upsert.side_effect = lambda sess, table, rows, **kw: captured_rows.extend(rows)
            write_signal(session, payload)
        assert captured_rows[0]["symbol"] == "NVDA"

    def test_upsert_conflict_cols_include_signal_id(self):
        from app.signals.writer import write_signal
        session = MagicMock()
        payload = _make_payload()
        captured_kwargs = {}
        with patch("app.signals.writer.upsert_rows") as mock_upsert:
            mock_upsert.side_effect = lambda sess, table, rows, **kw: captured_kwargs.update(kw)
            write_signal(session, payload)
        assert "signal_id" in captured_kwargs.get("conflict_cols", [])
