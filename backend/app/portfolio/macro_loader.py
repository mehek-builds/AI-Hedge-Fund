"""Read latest-vintage macro values for the 6 components used by Phase 4 macro scorer (FR-4.1, FR-1.5).

Queries `macro_indicators` using a point-in-time filter:
  WHERE date <= :as_of AND ingestion_timestamp <= :as_of
This mirrors the FR-1.5 semantics established in Phase 1 (price_bars, earnings_events).

Gap SC-1b: `load_macro_snapshot()` reads the persisted composite_score and
score_components from macro_indicators (written by the macro ingestion flow after
migration 0003). The RL state builder and MoE meta-controller source the score from
here — never recomputed on the fly — so sizing decisions are fully replayable even
if the scoring algorithm changes in a future iteration.

All SQL uses SQLAlchemy `text()` with bound parameters — no f-string interpolation
(T-04-11). Each series query uses LIMIT 1 to prevent unbounded result sets (T-04-12).
"""
from datetime import datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.portfolio.macro import compute_macro_score, score_component, COMPONENT_NAMES

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


def load_macro_snapshot(
    session: Session,
    as_of: datetime,
) -> tuple[int, dict[str, int]]:
    """Return (composite_score, score_components) as persisted in macro_indicators.

    Reads the composite_score and score_components columns written by the macro
    ingestion flow (migration 0003, gap SC-1b). Sourcing the score from DB ensures
    the RL state builder replays exactly the score that was live at decision time,
    even if the scoring algorithm changes in a future iteration.

    Falls back to computing from raw component readings if no persisted snapshot
    exists (e.g. pre-migration data or test environments without the flow running).

    Args:
        session: Synchronous SQLAlchemy Session.
        as_of: Point-in-time reference (FR-1.5 semantics).

    Returns:
        (composite_score, score_components) where score_components maps each
        COMPONENT_NAME to its individual -1/0 contribution.
    """
    row = session.execute(
        text(
            """
            SELECT composite_score, score_components
            FROM macro_indicators
            WHERE composite_score IS NOT NULL
              AND date <= :as_of
              AND ingestion_timestamp <= :as_of
            ORDER BY date DESC, ingestion_timestamp DESC
            LIMIT 1
            """
        ),
        {"as_of": as_of},
    ).fetchone()

    if row and row[0] is not None:
        score: int = int(row[0])
        components: dict[str, int] = dict(row[1]) if row[1] else {}
        return score, components

    # Fallback: compute from raw series readings (pre-migration data).
    raw = load_latest_macro_components(session, as_of)
    components = {name: score_component(name, raw.get(name)) for name in COMPONENT_NAMES}
    score = max(-6, min(0, sum(components.values())))
    return score, components
