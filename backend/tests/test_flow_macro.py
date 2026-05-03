import pandas as pd
import pytest
from datetime import date
from unittest.mock import MagicMock


def _fake_fred(series_values: dict[str, dict]):
    """series_values: {series_id: {date: value}}."""
    fred = MagicMock()

    def get_series(series_id, observation_start=None):
        data = series_values.get(series_id, {})
        idx = pd.to_datetime(list(data.keys()))
        return pd.Series(list(data.values()), index=idx)

    fred.get_series.side_effect = get_series
    fred.get_series_first_release.return_value = None
    return fred


def test_fred_series_count():
    from app.flows.macro import FRED_SERIES
    # 6+ series (DGS10/DGS2 = 2, Sahm, LEI, ISM proxy, JPY, AUD = 5 more = 7 total)
    assert len(FRED_SERIES) >= 6
    assert "DGS10" in FRED_SERIES
    assert "DGS2" in FRED_SERIES
    assert "SAHMCURRENT" in FRED_SERIES


def test_ingest_macro_writes_rows(db_engine):
    from app.flows.macro import ingest_macro_daily, FRED_SERIES
    fred = _fake_fred({sid: {"2026-05-01": 1.23} for sid in FRED_SERIES})
    n = ingest_macro_daily(lookback_days=30, fred_client=fred)
    assert n == len(FRED_SERIES)


def test_ingest_macro_idempotent(db_engine):
    from app.flows.macro import ingest_macro_daily
    fred = _fake_fred({"DGS10": {"2026-05-01": 4.5}})
    # Run twice — second must not error
    ingest_macro_daily(lookback_days=30, fred_client=fred)
    ingest_macro_daily(lookback_days=30, fred_client=fred)


def test_deploy_callable():
    from app.flows.macro import deploy
    assert callable(deploy)
