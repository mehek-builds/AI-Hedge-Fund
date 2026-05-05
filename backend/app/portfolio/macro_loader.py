"""Read latest-vintage macro values for the 6 components used by Phase 4 macro scorer (FR-4.1, FR-1.5).

Queries `macro_indicators` using a point-in-time filter:
  WHERE date <= :as_of AND ingestion_timestamp <= :as_of
This mirrors the FR-1.5 semantics established in Phase 1 (price_bars, earnings_events).

All SQL uses SQLAlchemy `text()` with bound parameters — no f-string interpolation
(T-04-11). Each series query uses LIMIT 1 to prevent unbounded result sets (T-04-12).
"""
from datetime import datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import text
from sqlalchemy.orm import Session

# Mapping from FRED/derived series_id -> component name used by macro.py scorer.
# Keys must match series_id values stored in macro_indicators.
# Values must match COMPONENT_NAMES in app.portfolio.macro.
SERIES_TO_COMPONENT: dict[str, str] = {
    "T10Y2Y": "yield_curve",
    "SAHMREALTIME": "sahm",
    "USALOLITONOSM": "lei",
    "MANEMP": "ism_pmi",
    "HYG_LQD_SPREAD": "hyg_lqd_spread",
    "JPY_AUD_CARRY": "jpy_aud_carry",
}


def load_latest_macro_components(
    session: Session,
    as_of: datetime,
) -> dict[str, Optional[Decimal]]:
    """Return latest-vintage values for all 6 macro components as of *as_of*.

    For each series_id, picks the row that satisfies:
      - date <= as_of  (observation is on or before the reference date)
      - ingestion_timestamp <= as_of  (FR-1.5: only data visible at as_of)
    then selects the latest by (date DESC, vintage_date DESC).

    Missing series (no qualifying row) are represented as None in the output,
    so downstream compute_macro_score treats them as neutral (score contribution 0).

    Args:
        session: Synchronous SQLAlchemy Session (from sync_session() context manager).
        as_of: Point-in-time reference. Only rows ingested on or before this timestamp
               are considered.

    Returns:
        Dict with exactly 6 keys matching COMPONENT_NAMES in app.portfolio.macro.
        Values are Decimal or None.
    """
    out: dict[str, Optional[Decimal]] = {c: None for c in SERIES_TO_COMPONENT.values()}

    for series_id, component in SERIES_TO_COMPONENT.items():
        row = session.execute(
            text(
                """
                SELECT value FROM macro_indicators
                WHERE series_id = :series_id
                  AND date <= :as_of
                  AND ingestion_timestamp <= :as_of
                ORDER BY date DESC, vintage_date DESC NULLS LAST
                LIMIT 1
                """
            ),
            {"series_id": series_id, "as_of": as_of},
        ).fetchone()
        out[component] = Decimal(str(row[0])) if row and row[0] is not None else None

    return out
