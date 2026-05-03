---
phase: 1
slug: infrastructure-data-foundation
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-05-02
---

# Phase 1 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 8.x (backend), vitest (Next.js) |
| **Config file** | `backend/pytest.ini` — Wave 0 installs |
| **Quick run command** | `cd backend && pytest tests/unit/ -q` |
| **Full suite command** | `cd backend && pytest tests/ -q && cd ../frontend && npm run test` |
| **Estimated runtime** | ~30 seconds |

---

## Sampling Rate

- **After every task commit:** Run `cd backend && pytest tests/unit/ -q`
- **After every plan wave:** Run full suite
- **Before `/gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** 30 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | Status |
|---------|------|------|-------------|-----------|-------------------|--------|
| 1-01-01 | 01 | 1 | FR-1.1 | integration | `docker compose ps` shows 6 services healthy | ⬜ pending |
| 1-01-02 | 01 | 1 | FR-1.2 | integration | `psql -c "\dt"` lists all 6 hypertables | ⬜ pending |
| 1-01-03 | 01 | 1 | FR-1.3 | manual | Railway restart → data persists | ⬜ pending |
| 1-01-04 | 01 | 2 | FR-1.4 | CI | GitHub Actions workflow completes green | ⬜ pending |
| 1-01-05 | 01 | 1 | FR-1.5 | unit | `pytest tests/test_point_in_time.py` exits 0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `backend/tests/test_point_in_time.py` — stub for FR-1.5 as_of query test
- [ ] `backend/tests/test_schema.py` — stub verifying all 6 hypertables accept writes
- [ ] `backend/tests/conftest.py` — shared fixtures (test DB connection, cleanup)
- [ ] `pytest`, `pytest-asyncio`, `sqlalchemy[asyncio]`, `asyncpg` installed in backend

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Railway persistent volume survives restart | FR-1.3 | Requires Railway cloud environment | Restart TimescaleDB service in Railway dashboard; confirm data persists via `psql` |
| Railway auto-deploy disabled for RL trainer | FR-1.4 | Railway dashboard config | Verify in Railway service settings that RL trainer has manual deploy only |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 30s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
