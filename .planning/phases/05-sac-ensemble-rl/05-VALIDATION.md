---
phase: 5
slug: sac-ensemble-rl
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-05-04
---

# Phase 5 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 9.x |
| **Config file** | `backend/pytest.ini` |
| **Quick run command** | `cd backend && pytest tests/rl/ -v --tb=short -k "not integration and not perf"` |
| **Full suite command** | `cd backend && pytest tests/ -v --tb=short -k "not integration and not perf"` |
| **Estimated runtime** | ~5 seconds (unit), ~15 seconds (full non-integration) |

---

## Sampling Rate

- **After every task commit:** Run `cd backend && pytest tests/rl/ -v --tb=short -k "not integration and not perf"`
- **After every plan wave:** Run `cd backend && pytest tests/ -v --tb=short -k "not integration and not perf"`
- **Before `/gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** 15 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | Status |
|---------|------|------|-------------|-----------|-------------------|--------|
| 05-01-01 | 01 | 0 | FR-5.1, FR-5.3 | unit | `pytest tests/rl/test_sac_agent.py -v` | ⬜ pending |
| 05-01-02 | 01 | 0 | FR-5.2 | unit | `pytest tests/rl/test_per_buffer.py -v` | ⬜ pending |
| 05-01-03 | 01 | 0 | FR-5.4 | unit | `pytest tests/rl/test_transformer_encoder.py -v` | ⬜ pending |
| 05-01-04 | 01 | 0 | FR-5.5 | unit | `pytest tests/rl/test_moe_controller.py -v` | ⬜ pending |
| 05-01-05 | 01 | 0 | FR-5.6 | unit | `pytest tests/rl/test_diversity.py -v` | ⬜ pending |
| 05-01-06 | 01 | 0 | FR-5.7 | unit | `pytest tests/rl/test_trainer.py -v` | ⬜ pending |
| 05-01-07 | 01 | 0 | FR-5.7 | migration | `cd backend && alembic upgrade head` | ⬜ pending |
| 05-02-01 | 02 | 1 | FR-5.3 | unit | `pytest tests/rl/test_sac_agent.py::test_beta_actor -v` | ⬜ pending |
| 05-02-02 | 02 | 1 | FR-5.1 | unit | `pytest tests/rl/test_sac_agent.py::test_distinct_init -v` | ⬜ pending |
| 05-02-03 | 02 | 1 | FR-5.4 | unit | `pytest tests/rl/test_transformer_encoder.py::test_layer_count -v` | ⬜ pending |
| 05-03-01 | 03 | 2 | FR-5.2 | unit | `pytest tests/rl/test_per_buffer.py::test_db_push -v` | ⬜ pending |
| 05-04-01 | 04 | 3 | FR-5.5 | unit | `pytest tests/rl/test_moe_controller.py::test_blend_all_five -v` | ⬜ pending |
| 05-05-01 | 05 | 4 | FR-5.6 | unit | `pytest tests/rl/test_diversity.py::test_alert_fires -v` | ⬜ pending |
| 05-06-01 | 06 | 5 | FR-5.7 | unit | `pytest tests/rl/test_trainer.py::test_checkpoint_every_1000 -v` | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `backend/tests/rl/__init__.py` — test package
- [ ] `backend/tests/rl/test_sac_agent.py` — failing stubs for FR-5.1, FR-5.3
- [ ] `backend/tests/rl/test_per_buffer.py` — failing stubs for FR-5.2
- [ ] `backend/tests/rl/test_transformer_encoder.py` — failing stubs for FR-5.4
- [ ] `backend/tests/rl/test_moe_controller.py` — failing stubs for FR-5.5
- [ ] `backend/tests/rl/test_diversity.py` — failing stubs for FR-5.6
- [ ] `backend/tests/rl/test_trainer.py` — failing stubs for FR-5.7
- [ ] `backend/alembic/versions/0004_rl_infra.py` — rl_checkpoints + rl_diversity_alerts tables

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Railway manual deploy gate | FR-5.7 | Requires Railway CLI + production credentials | Verify `railway.toml` has `deployTrigger = "manual"` for rl-trainer service; confirm CI yml excludes rl/ profile |
| Transformer pre-training convergence | FR-5.4 | Needs training run with real earnings data | Run `python -m rl.pretrain` with 8+ quarters of earnings_events data; verify loss decreases over 10 epochs |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 15s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
