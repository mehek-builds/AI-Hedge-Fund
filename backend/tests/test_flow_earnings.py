

SAMPLE_INCOME = [
    {"date": "2026-04-30", "period": "Q1", "calendarYear": 2026,
     "eps": 1.50, "revenue": 1.0e9, "operatingIncome": 2.0e8,
     "weightedAverageShsOut": 5_000_000_000},
    {"date": "2026-01-31", "period": "Q4", "calendarYear": 2025,
     "eps": 1.40, "revenue": 9.5e8, "operatingIncome": 1.9e8,
     "weightedAverageShsOut": 5_000_000_000},
]
SAMPLE_SURPRISES = [
    {"date": "2026-04-30", "actualEarningResult": 1.55, "estimatedEarning": 1.45},
]


def _fake_http(income_map: dict, surprise_map: dict):
    def get(path: str, params=None):
        if "/income-statement/" in path:
            sym = path.split("/income-statement/")[1]
            return income_map.get(sym, [])
        if "/earnings-surprises/" in path:
            sym = path.split("/earnings-surprises/")[1]
            return surprise_map.get(sym, [])
        return []
    return get


def test_parse_fmp_response():
    from app.flows.earnings import _parse_fmp_response
    rows = _parse_fmp_response(SAMPLE_INCOME, SAMPLE_SURPRISES, "AAPL")
    assert len(rows) == 2
    r0 = rows[0]
    assert r0["symbol"] == "AAPL"
    assert r0["fiscal_quarter"] == "2026Q1"
    assert r0["eps_actual"] == 1.55  # from surprise (preferred over income)
    assert r0["eps_estimate"] == 1.45
    assert r0["guidance_direction"] == "none"


def test_guidance_direction_is_check_constraint_safe():
    from app.flows.earnings import _parse_fmp_response
    rows = _parse_fmp_response(SAMPLE_INCOME, [], "X")
    allowed = {"up", "down", "flat", "none", "withdrawn"}
    assert all(r["guidance_direction"] in allowed for r in rows)


def test_ingest_earnings_writes_rows(db_engine, monkeypatch):
    from app.flows import earnings as mod
    monkeypatch.setattr(mod, "current_sp500_universe", lambda: ["AAPL"])
    getter = _fake_http({"AAPL": SAMPLE_INCOME}, {"AAPL": SAMPLE_SURPRISES})
    n = mod.ingest_earnings_daily(quarters=8, http_override=getter)
    assert n == 2


def test_ingest_earnings_idempotent(db_engine, monkeypatch):
    from app.flows import earnings as mod
    monkeypatch.setattr(mod, "current_sp500_universe", lambda: ["AAPL"])
    getter = _fake_http({"AAPL": SAMPLE_INCOME}, {"AAPL": SAMPLE_SURPRISES})
    mod.ingest_earnings_daily(quarters=8, http_override=getter)
    mod.ingest_earnings_daily(quarters=8, http_override=getter)


def test_missing_operating_income_handled():
    from app.flows.earnings import _parse_fmp_response
    income = [{"date": "2026-04-30", "period": "Q1", "calendarYear": 2026,
               "eps": 1.50, "revenue": 1e9}]  # no operatingIncome key
    rows = _parse_fmp_response(income, [], "X")
    assert rows[0]["operating_income"] is None
