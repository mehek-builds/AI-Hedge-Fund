import io
import zipfile



def _make_fake_zip(csv_text: str) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("F-F_Research_Data_5_Factors_2x3_daily.CSV", csv_text)
    return buf.getvalue()


SAMPLE_CSV = (
    "This file was created by CMPT_ME_BEME_RETS using the 202604 CRSP database.\n"
    "\n"
    ",Mkt-RF,SMB,HML,RMW,CMA,RF\n"
    "20260501,  0.45, -0.10,  0.20,  0.05,  0.00,  0.02\n"
    "20260502, -0.30,  0.15,  0.10, -0.05,  0.05,  0.02\n"
    "\n"
    "Annual Factors: January-December\n"
    "2025,  10.00,  2.00,  3.00, 1.5, 0.5, 4.0\n"
)


def test_parse_ff5_basic_rows():
    from app.flows.ff5 import parse_ff5_csv
    rows = parse_ff5_csv(_make_fake_zip(SAMPLE_CSV))
    assert len(rows) == 2
    r0 = rows[0]
    assert r0["date"].isoformat() == "2026-05-01"
    # 0.45 percent -> 0.0045 decimal
    assert abs(r0["mkt_rf"] - 0.0045) < 1e-9
    assert abs(r0["smb"] - (-0.0010)) < 1e-9


def test_parse_skips_annual_block():
    from app.flows.ff5 import parse_ff5_csv
    rows = parse_ff5_csv(_make_fake_zip(SAMPLE_CSV))
    # 2 daily rows; annual "2025" row has 4-digit token, must be skipped
    assert len(rows) == 2


def test_ingest_ff5_writes_rows(db_engine):
    from app.flows.ff5 import ingest_ff5_weekly
    n = ingest_ff5_weekly(downloader=lambda: _make_fake_zip(SAMPLE_CSV))
    assert n == 2


def test_ingest_ff5_idempotent(db_engine):
    from app.flows.ff5 import ingest_ff5_weekly
    z = _make_fake_zip(SAMPLE_CSV)
    ingest_ff5_weekly(downloader=lambda: z)
    ingest_ff5_weekly(downloader=lambda: z)


def test_deploy_callable():
    from app.flows.ff5 import deploy
    assert callable(deploy)
