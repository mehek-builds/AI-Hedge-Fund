---
phase: 7
slug: alpaca-execution-alerting
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-05-13
---

# Phase 7 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 9.0.3 |
| **Config file** | `backend/pytest.ini` |
| **Quick run command** | `cd backend && pytest tests/ -v --tb=short -k "not integration"` |
| **Full suite command** | `DATABASE_URL_SYNC=postgresql://pead:pead@localhost:5432/pead pytest tests/ -v` |
| **Estimated runtime** | ~30 seconds (unit), ~60 seconds (with integration) |

---

## Sampling Rate

- **After every task commit:** Run `cd backend && pytest tests/ -v --tb=short -k "not integration"`
- **After every plan wave:** Run `DATABASE_URL_SYNC=postgresql://pead:pead@localhost:5432/pead pytest tests/ -v`
- **Before `/gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** 60 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 07-01-01 | 01 | 1 | FR-8.1 | integration | `pytest tests/test_alerts_schema.py -x` | ❌ W0 | ⬜ pending |
| 07-02-01 | 02 | 1 | FR-7.1 | unit | `pytest tests/execution/test_broker.py -x` | ❌ W0 | ⬜ pending |
| 07-02-02 | 02 | 1 | FR-7.6 | unit | `pytest tests/execution/test_broker.py::test_short_blocked_by_flag -x` | ❌ W0 | ⬜ pending |
| 07-03-01 | 03 | 2 | FR-7.2 | unit | `pytest tests/execution/test_position_sync.py -x` | ❌ W0 | ⬜ pending |
| 07-03-02 | 03 | 2 | FR-7.3 | unit | `pytest tests/execution/test_orphan_detector.py -x` | ❌ W0 | ⬜ pending |
| 07-04-01 | 04 | 2 | FR-7.4 | unit | `pytest tests/alerting/test_dispatcher.py -x` | ❌ W0 | ⬜ pending |
| 07-04-02 | 04 | 2 | FR-7.5 | unit | `pytest tests/alerting/test_rate_limiter.py -x` | ❌ W0 | ⬜ pending |
| 07-04-03 | 04 | 2 | FR-8.3/8.4 | unit | `pytest tests/alerting/test_dispatcher.py::test_redis_publish -x` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `backend/tests/execution/__init__.py` — execution test package
- [ ] `backend/tests/execution/test_broker.py` — covers FR-7.1, FR-7.6 (bracket order + short flag)
- [ ] `backend/tests/execution/test_position_sync.py` — covers FR-7.2 (reconciliation)
- [ ] `backend/tests/execution/test_orphan_detector.py` — covers FR-7.3 (orphan cancel)
- [ ] `backend/tests/alerting/__init__.py` — alerting test package
- [ ] `backend/tests/alerting/test_dispatcher.py` — covers FR-7.4, FR-8.3, FR-8.4
- [ ] `backend/tests/alerting/test_rate_limiter.py` — covers FR-7.5 (burst test: 10 events → 3 deliveries)
- [ ] `backend/tests/test_alerts_schema.py` — covers FR-8.1 (DB-gated)

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Bracket order submitted to Alpaca paper account | FR-7.1 | Requires live Alpaca paper credentials | POST /api/v1/orders with valid signal payload; verify order appears in Alpaca paper dashboard |
| Phase 7 startup blocked when gate_status = 'fail' | SC7 | Requires running service | Start service with no `backtest_gate_pass` in DB, confirm RuntimeError logged and service exits |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 60s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
