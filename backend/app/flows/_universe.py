"""S&P 500 universe lookup, used by all flows that need a ticker list."""
from sqlalchemy import select

from app.flows._base import sync_session
from app.models.sp500_constituents import SP500Constituent

# Fallback used when sp500_constituents table is empty (Wave 2 race:
# the constituent flow is in plan 02-04, this flow is in plan 02-02; both run
# in Wave 2 against an empty table on first execution.)
FALLBACK_SP500 = [
    "AAPL", "MSFT", "GOOGL", "AMZN", "META", "NVDA", "TSLA",
    "BRK.B", "UNH", "JNJ", "JPM", "XOM", "V", "PG", "MA",
    "HD", "CVX", "MRK", "ABBV", "LLY", "PEP", "KO", "BAC",
    "AVGO", "PFE", "COST", "MCD", "TMO", "WMT", "DIS", "CSCO",
    "ACN", "VZ", "ABT", "ADBE", "DHR", "TXN", "PM", "CRM",
    "NEE", "NKE", "RTX", "INTC", "QCOM", "HON", "AMD", "UPS",
    "LOW", "INTU", "IBM", "GS", "CAT", "AXP", "SPGI", "ISRG",
    "BLK", "DE", "MDLZ", "GILD", "ADI", "REGN", "MU", "AMAT",
    "SYK", "BKNG", "ADP", "NOW", "MMC", "CI", "ZTS", "PYPL",
    "PANW", "ETN", "LRCX", "BSX", "EOG", "SLB", "ELV", "WM",
    "HCA", "VRTX", "GE", "AON", "CME", "FDX", "ITW", "ICE",
    "MCO", "EW", "SO", "DUK", "PLD", "PSA", "APD", "F",
    "GM", "NFLX", "ORCL", "UBER", "ABNB", "DDOG", "SNOW", "NET",
]


def current_sp500_universe() -> list[str]:
    """Return active S&P 500 tickers. Falls back to hard-coded list if table empty."""
    try:
        with sync_session() as s:
            rows = s.execute(
                select(SP500Constituent.symbol)
                .where(SP500Constituent.removed_date.is_(None))
            ).scalars().all()
        return list(rows) if rows else list(FALLBACK_SP500)
    except Exception:
        # DB not available (e.g. no connection) — use fallback
        return list(FALLBACK_SP500)
