---
phase: 6
slug: backtest-engine-validation-gate
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-05-12
---

# Phase 6 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 7.x |
| **Config file** | `backend/pytest.ini` |
| **Quick run command** | `cd backend && python -m pytest tests/backtest/ -x -q` |
| **Full suite command** | `cd backend && python -m pytest tests/ -q` |
| **Estimated runtime** | ~60 seconds (unit/integration), ~4 hours (full 2018-2023 replay) |

---

## Sampling Rate

- **After every task commit:** Run `cd backend && python -m pytest tests/backtest/ -x -q`
- **After every plan wave:** Run `cd backend && python -m pytest tests/ -q`
- **Before `/gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** 60 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 06-01-01 | 01 | 1 | FR-6.1 | T-6-01 | Injected future row absent from all backtest queries | unit | `cd backend && python -m pytest tests/backtest/test_backtest_as_of.py -x -q` | ❌ W0 | ⬜ pending |
| 06-01-02 | 01 | 1 | FR-6.1 | — | backtest_runs schema has all required columns | unit | `cd backend && python -m pytest tests/backtest/test_backtest_schema.py -x -q` | ❌ W0 | ⬜ pending |
| 06-02-01 | 02 | 1 | FR-6.2 | — | No backtest-only signal definitions | unit | `cd backend && python -m pytest tests/backtest/test_backtest_uses_prod_engine.py -x -q` | ❌ W0 | ⬜ pending |
| 06-03-01 | 03 | 2 | FR-6.3 | — | Stats computed correctly on synthetic data | unit | `cd backend && python -m pytest tests/backtest/test_backtest_stats.py -x -q` | ❌ W0 | ⬜ pending |
| 06-03-02 | 03 | 2 | FR-6.4 | — | Gate pass/fail logic fires correct alert | unit | `cd backend && python -m pytest tests/backtest/test_backtest_gate.py -x -q` | ❌ W0 | ⬜ pending |
| 06-04-01 | 04 | 2 | FR-6.5 | — | Ex-2020 slice runs and reports Sharpe | integration | `cd backend && python -m pytest tests/backtest/test_backtest_e2e.py -x -q` | ❌ W0 | ⬜ pending |
| 06-04-02 | 04 | 2 | FR-6.6 | — | backtest_runs row queryable from DB | integration | `cd backend && python -m pytest tests/backtest/test_backtest_e2e.py::test_results_persisted -x -q` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `backend/tests/backtest/__init__.py` — test package
- [ ] `backend/tests/backtest/conftest.py` — shared fixtures (synthetic backtest data, mock DB session)
- [ ] `backend/tests/backtest/test_backtest_as_of.py` — stub for FR-6.1 look-ahead bias test
- [ ] `backend/tests/backtest/test_backtest_schema.py` — stub for backtest_runs schema
- [ ] `backend/tests/backtest/test_backtest_uses_prod_engine.py` — stub for FR-6.2 import graph
- [ ] `backend/tests/backtest/test_backtest_stats.py` — stub for FR-6.3 statistics
- [ ] `backend/tests/backtest/test_backtest_gate.py` — stub for FR-6.4 gate logic
- [ ] `backend/tests/backtest/test_backtest_e2e.py` — stub for FR-6.5/FR-6.6 end-to-end

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Full 2018-2023 replay completes under 4 hours | NFR-1 | Runtime too long for CI | Run `python backend/scripts/run_full_backtest.py --start 2018-01-01 --end 2023-12-31`, measure elapsed time |
| Phase 7 startup blocked when gate_status = 'fail' | FR-6.4 | Requires Phase 7 service to be running | Start Phase 7 service with gate_status='fail' in DB, confirm startup logs "GATE CHECK FAILED" and service exits |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 60s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
