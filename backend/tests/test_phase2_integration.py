"""Phase 2 end-to-end mocked integration test.

Drives all 6 flows in their natural execution order with synthetic source data,
then asserts each target table has at least one row.

These tests require a live PostgreSQL instance with Phase 2 schema applied
(`alembic upgrade head` inside the container). They are CI-gated per the
pattern established in Phase 1 and plans 02-01..02-04.
"""
from datetime import date, datetime, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock

import pandas as pd
import pytest
from sqlalchemy import text


# ─── Test fixtures ────────────────────────────────────────────────────────────


class _FakeBar:
    def __init__(self, ts, o, h, l, c, v):
        self.timestamp = ts
        self.open = o
        self.high = h
        self.low = l
        self.close = c
        self.volume = v
        self.vwap = (o + c) / 2


def _alpaca_client(symbols):
    client = MagicMock()
    resp = SimpleNamespace(data={
        sym: [_FakeBar(datetime(2026, 5, 1, tzinfo=timezone.utc),
                       100.0, 101.0, 99.5, 100.5, 1_000_000)]
        for sym in symbols
    })
    client.get_stock_bars.return_value = resp
    return client


def _fake_fred():
    fred = MagicMock()

    def get_series(sid, observation_start=None):
        return pd.Series([1.23, 1.24], index=pd.to_datetime(["2026-04-30", "2026-05-01"]))

    fred.get_series.side_effect = get_series
    fred.get_series_first_release.return_value = None
    return fred


def _ff5_zip_bytes():
    import io
    import zipfile
    csv = ",Mkt-RF,SMB,HML,RMW,CMA,RF\n20260501,0.45,-0.10,0.20,0.05,0.00,0.02\n"
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("F-F_Research_Data_5_Factors_2x3_daily.CSV", csv)
    return buf.getvalue()


def _fmp_http():
    def get(path, params=None):
        if "/income-statement/" in path:
            return [{"date": "2026-04-30", "period": "Q1", "calendarYear": 2026,
                     "eps": 1.5, "revenue": 1e9, "operatingIncome": 2e8,
                     "weightedAverageShsOut": 5_000_000_000}]
        if "/earnings-surprises/" in path:
            return [{"date": "2026-04-30",
                     "actualEarningResult": 1.55, "estimatedEarning": 1.45}]
        return []
    return get


def _wiki_tables():
    current = pd.DataFrame({
        "Symbol": ["AAPL", "HYG", "LQD"],
        "Security": ["Apple", "iShares HY", "iShares IG"],
        "Date added": ["1980-12-12", "2010-01-01", "2010-01-01"],
    })
    changes = pd.DataFrame({
        "Date": ["2018-06-01"],
        "Added Ticker": ["NEW"],
        "Removed Ticker": ["OLD"],
    })
    return [current, changes]


# ─── Sync engine helper ───────────────────────────────────────────────────────


def _sync_engine():
    """Create a sync SQLAlchemy engine for test assertions."""
    from sqlalchemy import create_engine
    sync_url = __import__("app.config", fromlist=["settings"]).settings.DATABASE_URL_SYNC
    return create_engine(sync_url)


# ─── The integration tests ────────────────────────────────────────────────────


def test_all_six_flows_write_to_their_tables(monkeypatch):
    """After running all 6 flows with mocked sources, each target table has rows."""
    from app.flows import (
        prices as prices_mod,
        macro as macro_mod,
        ff5 as ff5_mod,
        earnings as earn_mod,
        constituents as cons_mod,
        derived_macro as deriv_mod,
    )

    # Force in-memory or test-DB universe to a tiny set including HYG/LQD
    monkeypatch.setattr(prices_mod, "current_sp500_universe", lambda: ["AAPL", "HYG", "LQD"])
    monkeypatch.setattr(earn_mod, "current_sp500_universe", lambda: ["AAPL"])

    # 1. Constituents first (so universe is real for re-runs)
    cons_mod.sync_sp500_constituents_weekly(fetcher=lambda: _wiki_tables())

    # 2. Prices
    prices_mod._run_ingestion(lookback_days=2,
                              test_client=_alpaca_client(["AAPL", "HYG", "LQD"]))

    # 3. Macro (FRED)
    macro_mod.ingest_macro_daily(lookback_days=10, fred_client=_fake_fred())

    # 4. FF5
    z = _ff5_zip_bytes()
    ff5_mod.ingest_ff5_weekly(downloader=lambda: z)

    # 5. Earnings
    earn_mod.ingest_earnings_daily(quarters=4, http_override=_fmp_http())

    # 6. Derived (HYG/LQD spread) — depends on prices being present
    n_deriv = deriv_mod.compute_hyg_lqd_daily(lookback_days=10)
    assert n_deriv >= 1, "HYG/LQD spread must produce at least one row"

    # Verify each table received rows
    eng = _sync_engine()
    with eng.connect() as c:
        assert c.execute(text("SELECT count(*) FROM price_bars")).scalar() > 0
        assert c.execute(text("SELECT count(*) FROM macro_indicators")).scalar() > 0
        assert c.execute(text(
            "SELECT count(*) FROM macro_indicators WHERE series_id='HYG_LQD_SPREAD'"
        )).scalar() > 0
        assert c.execute(text("SELECT count(*) FROM ff5_factors")).scalar() > 0
        assert c.execute(text("SELECT count(*) FROM earnings_events")).scalar() > 0
        assert c.execute(text("SELECT count(*) FROM sp500_constituents")).scalar() > 0
    eng.dispose()


def test_sequence_is_idempotent(monkeypatch):
    """Running the full sequence twice does not error."""
    from app.flows import (
        prices as p, macro as m, ff5 as f, earnings as e,
        constituents as c, derived_macro as d,
    )
    monkeypatch.setattr(p, "current_sp500_universe", lambda: ["AAPL", "HYG", "LQD"])
    monkeypatch.setattr(e, "current_sp500_universe", lambda: ["AAPL"])
    z = _ff5_zip_bytes()
    wiki = lambda: _wiki_tables()
    client = _alpaca_client(["AAPL", "HYG", "LQD"])
    fred = _fake_fred()
    http = _fmp_http()

    for _ in range(2):
        c.sync_sp500_constituents_weekly(fetcher=wiki)
        p._run_ingestion(lookback_days=2, test_client=client)
        m.ingest_macro_daily(lookback_days=10, fred_client=fred)
        f.ingest_ff5_weekly(downloader=lambda: z)
        e.ingest_earnings_daily(quarters=4, http_override=http)
        d.compute_hyg_lqd_daily(lookback_days=10)


def test_derived_handles_missing_prices_gracefully():
    """If HYG/LQD bars are absent (e.g. very narrow lookback), flow returns 0 not raise."""
    from app.flows import derived_macro as d
    # lookback_days=0 → cutoff = now, so PriceBar.time >= now yields no rows
    n = d.compute_hyg_lqd_daily(lookback_days=0)
    assert n == 0
