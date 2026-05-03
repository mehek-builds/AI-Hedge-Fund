from datetime import date
import pandas as pd
import pytest


def _current_df():
    return pd.DataFrame({
        "Symbol": ["AAPL", "MSFT", "TSLA"],
        "Security": ["Apple Inc.", "Microsoft", "Tesla"],
        "Date added": ["1980-12-12", "1986-03-13", "2020-12-21"],
    })


def _changes_df():
    # Multi-index header in real Wikipedia; flat is fine for parser
    return pd.DataFrame({
        "Date": ["2018-06-01", "2020-12-21", "2022-09-15"],
        "Added Ticker": ["TSLA", "TSLA", "ABC"],
        "Removed Ticker": ["XYZ",   "OLD",   "XYZ"],
    })


def test_build_rows_includes_current_members():
    from app.flows.constituents import _build_constituent_rows
    rows = _build_constituent_rows(_current_df(), _changes_df(), date(2026, 5, 1))
    symbols = [r["symbol"] for r in rows]
    assert "AAPL" in symbols and "MSFT" in symbols and "TSLA" in symbols


def test_build_rows_marks_removed_with_removed_date():
    from app.flows.constituents import _build_constituent_rows
    rows = _build_constituent_rows(_current_df(), _changes_df(), date(2026, 5, 1))
    removed = [r for r in rows if r["removed_date"] is not None]
    removed_syms = {r["symbol"] for r in removed}
    assert "OLD" in removed_syms or "XYZ" in removed_syms


def test_build_rows_current_members_have_null_removed_date():
    from app.flows.constituents import _build_constituent_rows
    rows = _build_constituent_rows(_current_df(), _changes_df(), date(2026, 5, 1))
    for s in ("AAPL", "MSFT"):
        hits = [r for r in rows if r["symbol"] == s]
        assert any(r["removed_date"] is None for r in hits)


def test_sync_writes_to_db(db_engine):
    from app.flows.constituents import sync_sp500_constituents_weekly
    n = sync_sp500_constituents_weekly(fetcher=lambda: [_current_df(), _changes_df()])
    assert n > 0


def test_deploy_callable():
    from app.flows.constituents import deploy
    assert callable(deploy)
