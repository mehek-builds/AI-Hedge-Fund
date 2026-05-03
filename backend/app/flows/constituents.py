"""Wikipedia → sp500_constituents (current members + historical changes)."""
from __future__ import annotations
from datetime import date, datetime
from typing import Callable, Optional

import pandas as pd
from prefect import flow, task, get_run_logger
from prefect.client.schemas.schedules import CronSchedule

from app.flows._base import sync_session, upsert_rows
from app.models.sp500_constituents import SP500Constituent

WIKI_URL = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"


def _fetch_tables(url: str = WIKI_URL) -> list[pd.DataFrame]:
    # pandas.read_html uses lxml under the hood (declared in requirements)
    return pd.read_html(url)


def _safe_date(s) -> Optional[date]:
    if not s or (isinstance(s, float) and pd.isna(s)):
        return None
    try:
        return pd.to_datetime(str(s)).date()
    except Exception:
        return None


def _build_constituent_rows(
    current_df: pd.DataFrame,
    changes_df: pd.DataFrame,
    fetch_today: date,
) -> list[dict]:
    """Produce list of dicts for upsert.

    Strategy:
      1. Every row in current_df → (symbol, added_date, removed_date=NULL).
         added_date comes from current_df['Date added'] if present, else fetch_today.
      2. Every Removed-Ticker row in changes_df → look up its add date by scanning
         earlier Added-Ticker rows for the same ticker; emit (symbol, added, removed).
         If we can't find the add date, fall back to a sentinel old date (1957-03-04 = S&P 500 inception).
      3. For tickers that were Added in changes_df but are NOT currently in current_df,
         they must have been removed later — case 2 handles them.
    """
    rows: list[dict] = []
    current_symbols: set[str] = set()

    # Normalise current table column names — Wikipedia uses 'Symbol' or 'Ticker symbol'
    sym_col = next((c for c in current_df.columns if str(c).strip().lower() in
                    {"symbol", "ticker symbol", "ticker"}), None)
    added_col = next((c for c in current_df.columns if "added" in str(c).lower()), None)
    name_col = next((c for c in current_df.columns if str(c).strip().lower() in
                     {"security", "company"}), None)
    if sym_col is None:
        return rows

    for _, r in current_df.iterrows():
        sym = str(r[sym_col]).strip()
        if not sym or sym.lower() == "nan":
            continue
        current_symbols.add(sym)
        rows.append({
            "symbol": sym,
            "company_name": str(r[name_col]) if name_col else None,
            "added_date": _safe_date(r[added_col]) if added_col else fetch_today,
            "removed_date": None,
        })

    # Changes table: assume cols include Date, Added (Ticker, Security), Removed (Ticker, Security)
    # pandas reads the multi-header as ('Added', 'Ticker') etc.; columns may be flat or tuples.
    def _col(df, *cands):
        for c in df.columns:
            flat = " ".join(str(x).lower() for x in (c if isinstance(c, tuple) else (c,)))
            for cand in cands:
                if cand in flat:
                    return c
        return None

    date_c = _col(changes_df, "date")
    added_t_c = _col(changes_df, "added ticker", "added symbol", "added")
    removed_t_c = _col(changes_df, "removed ticker", "removed symbol", "removed")

    if date_c is None or removed_t_c is None:
        return rows

    # Index added events by ticker for fallback added_date lookup
    added_lookup: dict[str, date] = {}
    for _, r in changes_df.iterrows():
        t = str(r.get(added_t_c, "")).strip() if added_t_c is not None else ""
        d = _safe_date(r.get(date_c))
        if t and t.lower() != "nan" and d is not None:
            added_lookup.setdefault(t, d)

    INCEPTION = date(1957, 3, 4)
    for _, r in changes_df.iterrows():
        rt = str(r.get(removed_t_c, "")).strip() if removed_t_c is not None else ""
        if not rt or rt.lower() == "nan":
            continue
        rd = _safe_date(r.get(date_c))
        if rd is None:
            continue
        if rt in current_symbols:
            # Re-added ticker: emit a closed historical interval
            ad = added_lookup.get(rt, INCEPTION)
            if ad >= rd:
                ad = INCEPTION
        else:
            ad = added_lookup.get(rt, INCEPTION)
        rows.append({
            "symbol": rt,
            "company_name": None,
            "added_date": ad,
            "removed_date": rd,
        })

    return rows


def _run_constituents(fetcher: Optional[Callable] = None) -> int:
    """Core constituent sync logic — plain function, callable without Prefect runtime.

    Same pattern as prices._run_ingestion: extracted so integration tests can
    call this directly, bypassing the Prefect ephemeral server requirement.
    """
    try:
        logger = get_run_logger()
    except Exception:
        import logging
        logger = logging.getLogger(__name__)
    tables = (fetcher or _fetch_tables)()
    if len(tables) < 2:
        logger.error(f"Expected >=2 tables on Wikipedia page, got {len(tables)}")
        return 0
    rows = _build_constituent_rows(tables[0], tables[1], date.today())
    if not rows:
        return 0
    with sync_session() as s:
        # Conflict on (symbol, added_date) — same ticker added on the same date is the same row
        # NOTE: there is no unique index on (symbol, added_date) yet; use manual delete+insert
        # for symbols where rows changed.
        # Simpler approach: TRUNCATE-and-rewrite is unsafe (loses ingestion_timestamp history).
        # Pragmatic approach for v1: DELETE rows whose (symbol, added_date) we are re-asserting.
        from sqlalchemy import and_, delete
        from app.models.sp500_constituents import SP500Constituent as M
        keys = {(r["symbol"], r["added_date"]) for r in rows}
        for sym, ad in keys:
            s.execute(delete(M).where(and_(M.symbol == sym, M.added_date == ad)))
        # Now plain insert
        s.execute(M.__table__.insert(), rows)
    logger.info(f"Wrote {len(rows)} constituent rows")
    return len(rows)


@task(retries=2, retry_delay_seconds=30)
def fetch_and_upsert_constituents(fetcher: Optional[Callable] = None) -> int:
    return _run_constituents(fetcher=fetcher)


@flow(name="sync_sp500_constituents_weekly", retries=2, retry_delay_seconds=120)
def sync_sp500_constituents_weekly(fetcher: Optional[Callable] = None) -> int:
    return fetch_and_upsert_constituents(fetcher=fetcher)


def deploy() -> None:
    """Weekly Sunday 12:00 UTC — Wikipedia changes are infrequent."""
    sync_sp500_constituents_weekly.serve(
        name="sync-sp500-constituents-weekly",
        schedule=CronSchedule(cron="0 12 * * 0", timezone="UTC"),
        tags=["phase-2", "constituents"],
    )


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "deploy":
        deploy()
    else:
        sync_sp500_constituents_weekly()
