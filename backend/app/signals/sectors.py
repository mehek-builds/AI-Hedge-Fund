"""GICS sector map, sector forward P/E table, and sector hurdle rates.

Hardcoded per Phase 3 plan. No external API calls — sector P/E values are
plan-locked so signal computation stays deterministic and offline-testable.
"""
from decimal import Decimal
from typing import Final

# Simplified GICS buckets used across the signal engine.
SECTORS: Final[tuple[str, ...]] = (
    "Tech",
    "Healthcare",
    "Financials",
    "Consumer",
    "Energy",
    "Industrials",
    "Utilities",
    "Other",
)

# Hardcoded sector mapping for ~60 frequently-traded S&P 500 names.
# Anything not in this map falls through to "Other".
SECTOR_MAP: Final[dict[str, str]] = {
    # Tech
    "AAPL": "Tech", "MSFT": "Tech", "NVDA": "Tech", "GOOGL": "Tech", "GOOG": "Tech",
    "META": "Tech", "AMZN": "Tech", "TSLA": "Tech", "AVGO": "Tech", "ORCL": "Tech",
    "CRM": "Tech", "ADBE": "Tech", "AMD": "Tech", "INTC": "Tech", "CSCO": "Tech",
    "QCOM": "Tech", "TXN": "Tech", "IBM": "Tech", "NFLX": "Tech",
    # Healthcare (incl. biotech)
    "UNH": "Healthcare", "JNJ": "Healthcare", "LLY": "Healthcare", "PFE": "Healthcare",
    "ABBV": "Healthcare", "MRK": "Healthcare", "TMO": "Healthcare", "ABT": "Healthcare",
    "DHR": "Healthcare", "BMY": "Healthcare", "AMGN": "Healthcare", "GILD": "Healthcare",
    "REGN": "Healthcare", "VRTX": "Healthcare", "BIIB": "Healthcare",
    # Financials
    "JPM": "Financials", "BAC": "Financials", "WFC": "Financials", "GS": "Financials",
    "MS": "Financials", "C": "Financials", "BLK": "Financials", "SCHW": "Financials",
    "AXP": "Financials", "V": "Financials", "MA": "Financials",
    # Consumer (Discretionary + Staples merged for v1)
    "WMT": "Consumer", "HD": "Consumer", "PG": "Consumer", "KO": "Consumer",
    "PEP": "Consumer", "COST": "Consumer", "NKE": "Consumer", "MCD": "Consumer",
    "SBUX": "Consumer", "TGT": "Consumer", "LOW": "Consumer",
    # Energy
    "XOM": "Energy", "CVX": "Energy", "COP": "Energy", "SLB": "Energy", "EOG": "Energy",
    # Industrials
    "CAT": "Industrials", "BA": "Industrials", "HON": "Industrials", "UNP": "Industrials",
    "GE": "Industrials", "RTX": "Industrials", "LMT": "Industrials",
    # Utilities
    "NEE": "Utilities", "DUK": "Utilities", "SO": "Utilities", "AEP": "Utilities",
}

# Sector median forward P/E. Plan-locked values (broad-market estimates as of
# 2024-2025; refreshed manually each quarter — NOT fetched from any API).
SECTOR_FWD_PE: Final[dict[str, Decimal]] = {
    "Tech":         Decimal("28.0"),
    "Healthcare":   Decimal("18.0"),
    "Financials":   Decimal("13.0"),
    "Consumer":     Decimal("22.0"),
    "Energy":       Decimal("12.0"),
    "Industrials":  Decimal("19.0"),
    "Utilities":    Decimal("16.0"),
    "Other":        Decimal("18.0"),
}

# Sector hurdle rates for quality_score suppression (FR-3.3).
SECTOR_HURDLE: Final[dict[str, int]] = {
    "Tech":         60,
    "Healthcare":   55,
    "Financials":   50,
    "Consumer":     45,
    "Energy":       45,
    "Industrials":  45,
    "Utilities":    45,
    "Other":        45,
}


def sector_for(symbol: str) -> str:
    """Return the simplified GICS sector for a ticker, or 'Other' if unknown."""
    if not symbol:
        return "Other"
    return SECTOR_MAP.get(symbol.upper(), "Other")
