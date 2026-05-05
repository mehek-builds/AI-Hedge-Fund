"""Unit tests for the price bar ingestion flow.

These tests are fully offline — they mock the Alpaca client and the DB layer
(sync_session + upsert_rows) so no real database or API key is required.

Tests call _run_ingestion() directly to bypass the Prefect runtime (which
requires a running Prefect server when invoked via the @flow decorator).
The @flow decorator wraps _run_ingestion unchanged, so testing the inner
function is equivalent to testing the flow logic.
"""
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock, patch



class _FakeBar:
    def __init__(self, ts, o, h, low, c, v):
        self.timestamp = ts
        self.open = o
        self.high = h
        self.low = low
        self.close = c
        self.volume = v
        self.vwap = (o + c) / 2


def _fake_client_factory(symbols):
    client = MagicMock()
    resp = SimpleNamespace(data={
        sym: [_FakeBar(datetime(2026, 5, 1, tzinfo=timezone.utc),
                       100.0, 101.0, 99.5, 100.5, 1_000_000)]
        for sym in symbols
    })
    client.get_stock_bars.return_value = resp
    return client


def test_universe_fallback_when_table_empty():
    """current_sp500_universe() returns a non-empty list even when DB is unavailable."""
    from app.flows._universe import current_sp500_universe, FALLBACK_SP500
    # Patch sync_session to simulate empty/unavailable DB
    with patch("app.flows._universe.sync_session") as mock_ctx:
        mock_session = MagicMock()
        mock_session.execute.return_value.scalars.return_value.all.return_value = []
        mock_ctx.return_value.__enter__ = MagicMock(return_value=mock_session)
        mock_ctx.return_value.__exit__ = MagicMock(return_value=False)
        u = current_sp500_universe()
    assert isinstance(u, list)
    assert len(u) > 0
    assert all(isinstance(s, str) for s in u)
    # Should have fallen back to FALLBACK_SP500
    assert u == list(FALLBACK_SP500)


def test_ingest_prices_writes_to_db(monkeypatch):
    """_run_ingestion() calls upsert_rows for each batch of symbols."""
    from app.flows import prices as prices_mod

    symbols = ["AAPL", "MSFT"]
    monkeypatch.setattr(prices_mod, "current_sp500_universe", lambda: symbols)
    client = _fake_client_factory(symbols)

    upsert_call_count = []

    def fake_upsert(session, table, rows, conflict_cols, update_cols=None):
        upsert_call_count.append(len(rows))
        return len(rows)

    with patch("app.flows.prices.sync_session") as mock_ctx, \
         patch("app.flows.prices.upsert_rows", side_effect=fake_upsert):
        mock_ctx.return_value.__enter__ = MagicMock(return_value=MagicMock())
        mock_ctx.return_value.__exit__ = MagicMock(return_value=False)
        n = prices_mod._run_ingestion(lookback_days=2, test_client=client)

    # 2 symbols × 1 bar each = 2 rows total
    assert n == len(symbols), f"expected {len(symbols)} rows, got {n}"
    assert sum(upsert_call_count) == len(symbols)


def test_ingest_prices_idempotent(monkeypatch):
    """Running the ingestion twice with the same data does not error."""
    from app.flows import prices as prices_mod

    symbols = ["AAPL"]
    monkeypatch.setattr(prices_mod, "current_sp500_universe", lambda: symbols)
    client = _fake_client_factory(symbols)

    def fake_upsert(session, table, rows, conflict_cols, update_cols=None):
        return len(rows)

    with patch("app.flows.prices.sync_session") as mock_ctx, \
         patch("app.flows.prices.upsert_rows", side_effect=fake_upsert):
        mock_ctx.return_value.__enter__ = MagicMock(return_value=MagicMock())
        mock_ctx.return_value.__exit__ = MagicMock(return_value=False)
        # First run
        n1 = prices_mod._run_ingestion(lookback_days=2, test_client=client)
        # Second run — should not error (ON CONFLICT path simulated by same fake_upsert)
        n2 = prices_mod._run_ingestion(lookback_days=2, test_client=client)

    assert n1 == 1
    assert n2 == 1


def test_empty_response_does_not_raise(monkeypatch):
    """Flow logs warning and returns 0 when Alpaca returns empty bars for a symbol."""
    from app.flows import prices as prices_mod

    monkeypatch.setattr(prices_mod, "current_sp500_universe", lambda: ["XXXX"])
    client = MagicMock()
    client.get_stock_bars.return_value = SimpleNamespace(data={"XXXX": []})

    # upsert_rows should never be called since there are no rows
    with patch("app.flows.prices.upsert_rows") as mock_upsert:
        n = prices_mod._run_ingestion(lookback_days=2, test_client=client)

    assert n == 0
    mock_upsert.assert_not_called()


def test_flow_importable_and_callable():
    """ingest_prices_daily is a Prefect flow object with deploy() callable."""
    from app.flows.prices import ingest_prices_daily, deploy
    assert callable(ingest_prices_daily)
    assert callable(deploy)
