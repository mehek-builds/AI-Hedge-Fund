"""Ken French 5-factor daily returns ingestion → ff5_factors table."""
from __future__ import annotations
import io
import zipfile
from datetime import date, datetime
from typing import Callable, Optional

import requests
from prefect import flow, task, get_run_logger
from prefect.client.schemas.schedules import CronSchedule

from app.flows._base import sync_session, upsert_rows
from app.models.ff5_factors import FF5Factor

FF5_URL = (
    "https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/"
    "ftp/F-F_Research_Data_5_Factors_2x3_daily_CSV.zip"
)


def _download_zip() -> bytes:
    resp = requests.get(FF5_URL, timeout=60)
    resp.raise_for_status()
    return resp.content


def parse_ff5_csv(zip_bytes: bytes) -> list[dict]:
    """Extract the daily CSV from the zip and parse YYYYMMDD,Mkt-RF,SMB,HML,RMW,CMA,RF rows.

    Values in the source CSV are percent (e.g. 0.45 = 0.45%); we store as decimal
    (0.0045) by dividing by 100.
    """
    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
        name = next(n for n in zf.namelist() if n.lower().endswith(".csv"))
        raw = zf.read(name).decode("utf-8", errors="replace")
    rows: list[dict] = []
    for line in raw.splitlines():
        parts = [p.strip() for p in line.split(",")]
        if len(parts) != 7:
            continue
        ymd = parts[0]
        if not (ymd.isdigit() and len(ymd) == 8):
            # Skip header rows, blank lines, annual block trailer
            continue
        try:
            d = datetime.strptime(ymd, "%Y%m%d").date()
            mkt_rf, smb, hml, rmw, cma, rf = (float(p) / 100.0 for p in parts[1:])
        except ValueError:
            continue
        rows.append({
            "date": d,
            "mkt_rf": mkt_rf,
            "smb": smb,
            "hml": hml,
            "rmw": rmw,
            "cma": cma,
            "rf": rf,
        })
    return rows


@task(retries=3, retry_delay_seconds=60)
def fetch_and_upsert_ff5(downloader: Callable[[], bytes]) -> int:
    logger = get_run_logger()
    data = downloader()
    rows = parse_ff5_csv(data)
    logger.info(f"Parsed {len(rows)} FF5 daily rows")
    if not rows:
        return 0
    with sync_session() as s:
        n = upsert_rows(
            s, FF5Factor.__table__, rows,
            conflict_cols=["date"],
            update_cols=["mkt_rf", "smb", "hml", "rmw", "cma", "rf"],
        )
    return n


def _run_ff5(downloader: Optional[Callable[[], bytes]] = None) -> int:
    """Core FF5 ingestion logic — plain function, callable without Prefect runtime.

    Same pattern as prices._run_ingestion: extracted so integration tests can
    call this directly, bypassing the Prefect ephemeral server requirement.
    """
    try:
        logger = get_run_logger()
    except Exception:
        import logging
        logger = logging.getLogger(__name__)
    dl = downloader if downloader is not None else _download_zip
    data = dl()
    rows = parse_ff5_csv(data)
    logger.info(f"Parsed {len(rows)} FF5 daily rows")
    if not rows:
        return 0
    with sync_session() as s:
        n = upsert_rows(
            s, FF5Factor.__table__, rows,
            conflict_cols=["date"],
            update_cols=["mkt_rf", "smb", "hml", "rmw", "cma", "rf"],
        )
    return n


@flow(name="ingest_ff5_weekly", retries=2, retry_delay_seconds=120)
def ingest_ff5_weekly(downloader: Optional[Callable[[], bytes]] = None) -> int:
    return _run_ff5(downloader=downloader)


def deploy() -> None:
    """Weekly Saturday 06:00 UTC — Ken French publishes monthly + daily updates weekly."""
    ingest_ff5_weekly.serve(
        name="ingest-ff5-weekly",
        schedule=CronSchedule(cron="0 6 * * 6", timezone="UTC"),
        tags=["phase-2", "ff5"],
    )


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "deploy":
        deploy()
    else:
        ingest_ff5_weekly()
