---
phase: 1
slug: infrastructure-data-foundation
status: draft
nyquist_compliant: true
wave_0_complete: true
created: 2026-05-02
---

# Phase 1 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 9.0.3 + pytest-asyncio 1.3.0 (backend) |
| **Config file** | `backend/pytest.ini` — created in Plan 01-02 Task 2 |
| **Quick run command** | `cd backend && pytest tests/ -q -x` |
| **Full suite command** | `cd backend && pytest tests/ -v --tb=short` |
| **Estimated runtime** | ~30 seconds |

---

## Sampling Rate

- **After every task commit:** Run `cd backend && pytest tests/ -q -x`
- **After every plan wave:** Run full suite
- **Before `/gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** 30 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | Status |
|---------|------|------|-------------|-----------|-------------------|--------|
| 01-01-T1 | 01-01 | 1 | FR-1.1 | integration | `docker compose config --quiet && grep -q 'prefecthq/prefect:2-latest' docker-compose.yml && grep -q 'timescale/timescaledb:latest-pg15' docker-compose.yml` | ⬜ pending |
| 01-01-T2 | 01-01 | 1 | FR-1.1 | integration | `cd backend && python -c "from app.main import app; from app.worker import celery_app; print('imports ok')"` | ⬜ pending |
| 01-01-T3 | 01-01 | 1 | FR-1.1 | smoke | `docker compose up -d --build && (count=0; until [ $(docker compose ps --status healthy 2>/dev/null | grep -c 'healthy') -ge 6 ] || [ $count -gt 40 ]; do sleep 3; count=$((count+1)); done) && curl -fsS http://localhost:8000/health` | ⬜ pending |
| 01-02-T1 | 01-02 | 2 | FR-1.2 | integration | `cd backend && python -c "from app.models import PriceBar, EarningsEvent, Signal, RlTransition, MacroIndicator, PortfolioPosition; print('models ok')"` | ⬜ pending |
| 01-02-T2 | 01-02 | 2 | FR-1.2/FR-1.5 | integration | `cd backend && DATABASE_URL=postgresql+asyncpg://pead:devpass@localhost:5432/pead_trading alembic upgrade head && DATABASE_URL=postgresql+asyncpg://pead:devpass@localhost:5432/pead_trading pytest tests/ -v` | ⬜ pending |
| 01-03-T1 | 01-03 | 3 | FR-1.4 | CI | `python3 -c "import yaml; yaml.safe_load(open('.github/workflows/ci.yml'))"` exits 0 | ⬜ pending |
| 01-03-T2 | 01-03 | 3 | FR-1.3/FR-1.4 | CI | `python3 -c "import yaml; doc = yaml.safe_load(open('.github/workflows/deploy.yml')); assert 'rl_trainer' not in doc['jobs']['deploy']['strategy']['matrix']['service']; print('ok')"` | ⬜ pending |
| 01-03-T3 | 01-03 | 3 | FR-1.3 | manual | Railway restart → hypertable count still 6 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

All Wave 0 items are covered by Plan 01-02 Task 2 (TDD task, written first before migration):

- [x] `backend/pytest.ini` — pytest configuration with `asyncio_mode = auto` (01-02 Task 2)
- [x] `backend/tests/conftest.py` — async DB session fixture pointing at test DB (01-02 Task 2)
- [x] `backend/tests/test_health.py` — GET /health returns 200 with db connected (01-02 Task 2)
- [x] `backend/tests/test_schema.py` — hypertable existence, insert acceptance, ingestion_timestamp columns, idempotent migration (01-02 Task 2)
- [x] `backend/tests/test_as_of.py` — as_of filtering excludes future-ingested rows (01-02 Task 2, FR-1.5)
- [x] Framework install: pytest==9.0.3, pytest-asyncio==1.3.0, httpx==0.28.1 in backend/requirements.txt (01-01 Task 1)

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Railway persistent volume survives restart | FR-1.3 | Requires Railway cloud environment | Restart TimescaleDB service in Railway dashboard; confirm data persists via `psql -c "SELECT count(*) FROM timescaledb_information.hypertables"` returns 6 |
| Railway auto-deploy disabled for RL trainer | FR-1.4 | Railway dashboard config | Verify in Railway service settings that RL trainer has manual deploy only |

---

## Validation Sign-Off

- [x] All tasks have `<automated>` verify or Wave 0 dependencies
- [x] Sampling continuity: no 3 consecutive tasks without automated verify
- [x] Wave 0 covers all MISSING references (01-02 Task 2 is TDD — tests written before migration)
- [x] No watch-mode flags
- [x] Feedback latency < 30s
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** pending execution
