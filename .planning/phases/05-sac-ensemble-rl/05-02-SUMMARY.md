---
phase: 05-sac-ensemble-rl
plan: "02"
subsystem: rl
tags: [sac, beta-actor, ensemble, transformer, fr-5.1, fr-5.3, fr-5.4]
dependency_graph:
  requires: [05-01]
  provides: [BetaActor, seeded-SACEnsemble, transformer-3-layers]
  affects: [05-03, 05-04, 05-05]
tech_stack:
  added: [torch.distributions.Beta]
  patterns: [Beta policy, seeded-ensemble-init, hyperparameter-perturbation]
key_files:
  created:
    - backend/tests/rl/__init__.py
    - backend/tests/rl/conftest.py
    - backend/tests/rl/test_sac_agent.py
    - backend/tests/rl/test_transformer_encoder.py
  modified:
    - rl/sac_agent.py (lines 1-20 imports+constants, 29-68 BetaActor, 121 cont_actor, 150-165 select_action, 247-281 _perturb_cfg+SACEnsemble.__init__)
    - config.py (line 123 transformer_layers 4->3)
    - rl/transformer_encoder.py (line 30 docstring, line 43 n_layers default 4->3)
decisions:
  - "BetaActor replaces Gaussian+sigmoid: Beta(alpha,beta) naturally bounded (0,1), no squashing correction term needed in log_prob"
  - "BASE_SEEDS=[42,137,271,314,999] fixed at module level to ensure reproducible diversity"
  - "PARAM_FLOOR=1e-3 and LOG_AB clamps ensure alpha,beta never reach 0 (T-05-05 mitigation)"
  - "Transformer layer count changed 4->3 in both files atomically to avoid weight-shape mismatch"
metrics:
  duration: "~15 minutes"
  completed: "2026-05-12"
  tasks_completed: 3
  files_changed: 7
---

# Phase 5 Plan 02: SAC Core Divergence Fixes Summary

Three coupled SAC corrections applied atomically: BetaActor (FR-5.3), seeded ensemble init with hyperparameter perturbation (FR-5.1), and transformer layer count 4->3 in both config and encoder (FR-5.4).

## What Was Built

### Task 1 + 2: BetaActor + Seeded SACEnsemble (rl/sac_agent.py)

**BetaActor** replaces `ContinuousActor` throughout `rl/sac_agent.py`:
- `forward()` outputs `(alpha, beta)` each > 1e-3 via `log.exp() + PARAM_FLOOR`
- `sample()` calls `Beta(alpha, beta).rsample()`, clamps to `(1e-6, 1-1e-6)` before log_prob
- `deterministic()` returns `alpha / (alpha + beta)` as Beta distribution mean
- `entropy()` exposed for future use

**Seeded SACEnsemble** with `BASE_SEEDS = [42, 137, 271, 314, 999]`:
- Each agent initialized with distinct `torch.manual_seed(seed)` + `np.random.seed(seed)`
- `_perturb_cfg()` applies uniform `[-30%, +30%]` to `lr`, `gamma`, `tau` per agent
- `gamma` clamped to 0.9999 max to ensure strict discount validity
- Global RNG reset after init loop so callers are unaffected

### Task 3: Transformer Layer Count Fix (config.py + rl/transformer_encoder.py)

- `SACConfig.transformer_layers`: 4 -> 3
- `TransformerStateEncoder.__init__` default `n_layers`: 4 -> 3
- Docstring updated: "4-layer" -> "3-layer transformer encoder"

## Test Results: Plan 01 Stubs Flipped RED -> GREEN

| Test | FR | Status |
|------|----|--------|
| test_beta_actor | FR-5.3 | GREEN |
| test_distinct_init | FR-5.1 | GREEN |
| test_hyperparameter_perturbation | FR-5.1 | GREEN |
| test_macro_multiplier_no_grad | FR-5.3 | GREEN |
| test_layer_count | FR-5.4 | GREEN |
| test_encoder_config | FR-5.4 | GREEN |
| test_frozen_encoder | FR-5.4 | GREEN (was passing, still GREEN) |

All 7 RL tests pass. No regressions in the 247 other non-integration tests (2 pre-existing Celery task-registration failures are unrelated to this plan).

## Pre-trained Transformer Weights

**Any pre-trained transformer weights with 4 layers must be regenerated.** The layer count change from 4->3 means any saved `.pt` file will fail `load_state_dict()` due to shape mismatch. Since the system is pre-production, no weights have been saved yet; this is a forward-looking note for Phase 7+ when training begins.

## ContinuousActor -> BetaActor Migration Status

- `class ContinuousActor` removed from `rl/sac_agent.py` (grep count: 0)
- `class BetaActor` present (grep count: 1)
- `self.cont_actor = BetaActor(...)` in SACAgent.__init__ (1 occurrence)
- `from torch.distributions import Beta` import present (1 occurrence)
- Only remaining reference: test comment string in test_sac_agent.py (benign)
- No other files in the codebase referenced `ContinuousActor`

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Created test infrastructure missing from 05-01**
- **Found during:** Task 1 RED phase
- **Issue:** Plan 05-02 is wave 1 depending on wave 0 (05-01) test files; 05-01 runs in parallel and its test files did not exist yet in this worktree
- **Fix:** Created `backend/tests/rl/` subpackage with `__init__.py`, `conftest.py` (sys.path fix), `test_sac_agent.py`, and `test_transformer_encoder.py` with the exact stubs specified in 05-01-PLAN.md
- **Files modified:** backend/tests/rl/__init__.py, backend/tests/rl/conftest.py, backend/tests/rl/test_sac_agent.py, backend/tests/rl/test_transformer_encoder.py
- **Commit:** bfc99e4a

**2. [Rule 3 - Blocking] Added conftest.py for sys.path in rl tests**
- **Found during:** First test run attempt
- **Issue:** `import rl.sac_agent` failed with `ModuleNotFoundError` because `rl/` is at repo root, not inside `backend/`
- **Fix:** Created `backend/tests/rl/conftest.py` that inserts repo root into `sys.path`
- **Files modified:** backend/tests/rl/conftest.py (included in above commit)

### Tasks 1 and 2 Committed Together

Tasks 1 (BetaActor) and 2 (seeded SACEnsemble) both modify `rl/sac_agent.py`. The plan describes them as separate tasks but they were implemented as sequential edits to the same file and committed atomically in one commit (72783dee) to avoid a half-correct intermediate state where BetaActor exists but seeding is missing.

## Known Stubs

None. All implemented functionality is fully wired.

## Threat Flags

None. No new network endpoints, auth paths, file access, or schema changes introduced by this plan.

## Self-Check
