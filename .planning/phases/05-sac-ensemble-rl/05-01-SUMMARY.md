---
phase: 05-sac-ensemble-rl
plan: "01"
subsystem: rl-test-scaffolding
tags: [rl, testing, alembic, wave-0, tdd-red]
dependency_graph:
  requires: []
  provides:
    - backend/tests/rl/ subpackage (pytest-collectable)
    - Wave 0 failing test stubs for FR-5.1 through FR-5.7
    - Alembic migration 0004 (rl_checkpoints + rl_diversity_alerts)
  affects:
    - All Wave 1-5 plans (each plan's verify command targets tests in this plan)
    - backend/alembic/versions/ revision chain (0003 -> 0004)
tech_stack:
  added: []
  patterns:
    - pytest TDD RED-state stubs (failing until implementation arrives)
    - sys.path insertion for repo-root module access from backend/tests/
    - pytest.importorskip for optional-module gating
    - requires_db marker for DB-gated tests
key_files:
  created:
    - backend/tests/rl/__init__.py
    - backend/tests/rl/test_sac_agent.py
    - backend/tests/rl/test_per_buffer.py
    - backend/tests/rl/test_transformer_encoder.py
    - backend/tests/rl/test_moe_controller.py
    - backend/tests/rl/test_diversity.py
    - backend/tests/rl/test_trainer.py
    - backend/alembic/versions/0004_rl_phase5_tables.py
  modified: []
decisions:
  - "sys.path insertion pattern used in all rl test files to reach repo-root rl/ and config.py packages from backend/ pytest context"
  - "test_diversity.py uses pytest.importorskip so the entire module is skipped (not errored) until Wave 4 creates rl/diversity_monitor.py"
  - "Migration 0004 uses CREATE TABLE IF NOT EXISTS DDL (idempotent) consistent with project convention"
metrics:
  duration: 15m
  completed: "2026-05-12"
  tasks_completed: 3
  files_created: 8
  files_modified: 0
---

# Phase 5 Plan 01: Wave 0 Scaffolding - RL Test Stubs and Migration 0004 Summary

**One-liner:** Created 7 pytest failing-stub test files for FR-5.1 through FR-5.7 and Alembic migration 0004 adding rl_checkpoints + rl_diversity_alerts tables.

## What Was Built

Wave 0 scaffolding per the Nyquist rule: every downstream Wave 1-5 plan needs an automated verify command. This plan creates those test commands as failing stubs (RED state) so waves 1-5 can drive them to GREEN. The migration unblocks training loop checkpoint persistence.

### Test Files Created (backend/tests/rl/)

| File | FR | Test Functions |
|------|----|---------------|
| test_sac_agent.py | FR-5.1, FR-5.3 | test_beta_actor, test_distinct_init, test_hyperparameter_perturbation, test_macro_multiplier_no_grad |
| test_per_buffer.py | FR-5.2 | test_db_push (requires_db), test_priority_sampling |
| test_transformer_encoder.py | FR-5.4 | test_layer_count, test_encoder_config, test_frozen_encoder |
| test_moe_controller.py | FR-5.5 | test_blend_all_five, test_five_agent_blend_shape, test_regime_weights_sum |
| test_diversity.py | FR-5.6 | test_alert_fires_above_threshold, test_no_alert_below_threshold, test_compute_pairwise_diversity_signature, test_alert_dispatch |
| test_trainer.py | FR-5.7 | test_trainer_module_exists, test_checkpoint_at_1000_steps (requires_db), test_diversity_alerts_table_exists (requires_db) |

### Migration 0004

- Revision chain: 0003 -> 0004
- Table: `rl_checkpoints` (id UUID, step INT, agent_id SMALLINT, model_bytes BYTEA, total_steps INT, mean_reward_20 NUMERIC, is_active BOOL, created_at TIMESTAMPTZ)
- Table: `rl_diversity_alerts` (id UUID, max_similarity NUMERIC, agent_pair TEXT, epoch INT, created_at TIMESTAMPTZ)
- Both tables use `CREATE TABLE IF NOT EXISTS` (idempotent)
- Partial index `ix_rl_checkpoints_active` on (agent_id, step DESC) WHERE is_active = TRUE
- Descending index `ix_rl_diversity_alerts_created` on created_at

## RED-State Confirmation

After Wave 0 (before any Wave 1+ implementation), `pytest tests/rl/ -v` produces:

**FAILED (7):** These are expected failures driving Wave 1-5 implementation
- test_beta_actor - ContinuousActor not yet BetaActor (Wave 1)
- test_hyperparameter_perturbation - agents not yet perturbed (Wave 1)
- test_layer_count - transformer_layers still 4, not 3 (Wave 1)
- test_encoder_config - encoder still 4 layers (Wave 1)
- test_blend_all_five - blend() lacks agent_outputs param (Wave 3)
- test_five_agent_blend_shape - blend() API not updated (Wave 3)
- test_trainer_module_exists - worker/flows/rl_trainer.py missing (Wave 4)

**PASSED (5):** Tests that verify current functionality correctly
- test_distinct_init - agents already have distinct weights
- test_macro_multiplier_no_grad - float multiplication works
- test_priority_sampling - PER sampling logic already correct
- test_frozen_encoder - freeze() method already present
- test_regime_weights_sum - weights already sum to 1.0

**SKIPPED (4):**
- test_db_push - requires_db (no DATABASE_URL_SYNC in CI)
- test_checkpoint_at_1000_steps - requires_db
- test_diversity_alerts_table_exists - requires_db
- All 4 test_diversity tests - rl.diversity_monitor module doesn't exist yet (Wave 4)

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Added sys.path insertion to test_sac_agent.py and test_transformer_encoder.py**
- **Found during:** Task 1 verification
- **Issue:** `from rl.sac_agent import ...` raised ModuleNotFoundError because pytest runs from `backend/` but the `rl/` package is at repo root. The plan's template for test_per_buffer.py already included the sys.path fix but the other two files did not.
- **Fix:** Added `sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))` to test_sac_agent.py and test_transformer_encoder.py
- **Files modified:** backend/tests/rl/test_sac_agent.py, backend/tests/rl/test_transformer_encoder.py
- **Commit:** 83e3d31d

**2. [Rule 3 - Blocking] sys.path insertion added to test_moe_controller.py and test_diversity.py**
- **Found during:** Task 2 creation
- **Issue:** Same root-path issue: MoE and diversity tests need `rl.*` imports which are at repo root.
- **Fix:** Added sys.path insertion at top of both files proactively.
- **Files modified:** backend/tests/rl/test_moe_controller.py, backend/tests/rl/test_diversity.py
- **Commit:** ffec504a

## Known Stubs

All failing tests in this plan are intentional stubs (Wave 0 RED state). They are NOT production stubs or placeholder data - they are TDD contracts awaiting Wave 1-5 implementations. No UI-rendering stubs were created.

## Self-Check: PASSED

- backend/tests/rl/__init__.py: FOUND
- backend/tests/rl/test_sac_agent.py: FOUND (4 tests)
- backend/tests/rl/test_per_buffer.py: FOUND (2 tests)
- backend/tests/rl/test_transformer_encoder.py: FOUND (3 tests)
- backend/tests/rl/test_moe_controller.py: FOUND (3 tests)
- backend/tests/rl/test_diversity.py: FOUND (4 tests, currently skipped)
- backend/tests/rl/test_trainer.py: FOUND (3 tests, 2 db-gated)
- backend/alembic/versions/0004_rl_phase5_tables.py: FOUND (revision=0004, down_revision=0003)
- Commits: 83e3d31d (task 1), ffec504a (task 2), 34f329eb (task 3)
