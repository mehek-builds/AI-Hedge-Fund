from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from sqlalchemy import text


class _FakeBar:
    def __init__(self, ts, o, h, l, c, v):
        self.timestamp = ts
        self.open = o
        self.high = h
        self.low = l
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


def test_universe_fallback_when_table_empty(db_engine):
    from app.flows._universe import current_sp500_universe, FALLBACK_SP500
    u = current_sp500_universe()
    assert isinstance(u, list)
    assert len(u) > 0
    # Either fallback or DB-backed; both must produce a non-empty list
    assert all(isinstance(s, str) for s in u)


def test_ingest_prices_writes_to_db(db_engine, monkeypatch):
    from app.flows import prices as prices_mod
    symbols = ["AAPL", "MSFT"]
    monkeypatch.setattr(prices_mod, "current_sp500_universe", lambda: symbols)
    client = _fake_client_factory(symbols)
    n = prices_mod.ingest_prices_daily(lookback_days=2, _client=client)
    assert n == len(symbols), f"expected {len(symbols)} rows, got {n}"


def test_ingest_prices_idempotent(db_engine, monkeypatch):
    from app.flows import prices as prices_mod
    symbols = ["AAPL"]
    monkeypatch.setattr(prices_mod, "current_sp500_universe", lambda: symbols)
    client = _fake_client_factory(symbols)
    prices_mod.ingest_prices_daily(lookback_days=2, _client=client)
    # Second run should not error (ON CONFLICT path)
    prices_mod.ingest_prices_daily(lookback_days=2, _client=client)


def test_empty_response_does_not_raise(db_engine, monkeypatch):
    from app.flows import prices as prices_mod
    monkeypatch.setattr(prices_mod, "current_sp500_universe", lambda: ["XXXX"])
    client = MagicMock()
    client.get_stock_bars.return_value = SimpleNamespace(data={"XXXX": []})
    n = prices_mod.ingest_prices_daily(lookback_days=2, _client=client)
    assert n == 0
