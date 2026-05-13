---
phase: 05-sac-ensemble-rl
plan: "04"
subsystem: rl
tags: [moe, sac-ensemble, regime-weights, fr-5.5]
dependency_graph:
  requires: [05-02]
  provides: [MoEController.blend 5-agent API, SACEnsemble.select_action_per_agent]
  affects: [05-05]
tech_stack:
  added: []
  patterns:
    - Regime-to-agent weight projection via fixed bucket assignment (0,1->expansion / 2,3->caution / 4->crisis)
    - TDD RED/GREEN cycle with pytest stubs
key_files:
  created:
    - backend/tests/rl/__init__.py
    - backend/tests/rl/test_moe_controller.py
  modified:
    - rl/moe_controller.py
    - rl/sac_agent.py
    - rl/transformer_encoder.py
    - config.py
decisions:
  - Removed RegimeSpecialist class and _SPECIALISTS dict entirely; new design has no per-regime scaling wrappers
  - _SCORE_LOGITS extended from 4 keys (0..-3) to 7 keys (0..-6) to cover full macro composite range
  - select_action_per_agent added to SACEnsemble alongside (not replacing) select_action mean-average variant
metrics:
  duration_minutes: 25
  completed_date: "2026-05-12"
  tasks_completed: 2
  files_modified: 6
---

# Phase 5 Plan 4: MoE 5-Agent Blend Redesign Summary

**One-liner:** Redesigned MoEController.blend() to accept all 5 SAC agent outputs with regime-to-agent weight projection (0,1->expansion / 2,3->caution / 4->crisis), replacing the legacy 3-specialist architecture.

## What Was Built

### Task 1: MoEController.blend redesign (FR-5.5)

**New blend() signature:**
```python
def blend(
    self,
    agent_outputs: list[tuple[float, int]],  # exactly 5 (entry_size, hold_bin) tuples
    macro_score: int,                         # {0, -1, ..., -6}
    vix: float | None = None,
) -> MoEAction
```

**5-agent weight projection rule:**
- Agents 0, 1 share the expansion bucket: each gets `expansion_weight / 2`
- Agents 2, 3 share the caution bucket: each gets `caution_weight / 2`
- Agent 4 is the crisis bucket: gets `crisis_weight`
- Vector sums to 1.0 (regime weights sum to 1, projection preserves total)

Implemented via `_regime_weights_to_agent_weights(rw)` helper using fixed class attributes:
```python
_AGENT_TO_REGIME_BUCKET = np.array([0, 0, 1, 1, 2], dtype=np.int64)
_BUCKET_SIZES = np.array([2, 2, 1], dtype=np.float32)
```

**Extended macro score range:** `_SCORE_LOGITS` now covers {0, -1, -2, -3, -4, -5, -6} (was {0, -1, -2, -3}), required for Phase 4 macro composite score range.

**Removed:** `RegimeSpecialist` class, `_SPECIALISTS` dict, `specialists` parameter from `__init__`. Old `blend(raw_entries, raw_holds, ...)` signature fully replaced.

**Guard:** `ValueError` raised if `len(agent_outputs) != 5`.

### Task 2: SACEnsemble.select_action_per_agent (FR-5.5)

New method added to `SACEnsemble` returning raw per-agent outputs in stable index order:
```python
def select_action_per_agent(
    self,
    obs: np.ndarray,
    deterministic: bool = False,
) -> list[tuple[float, int]]:
```

- Returns list of exactly 5 `(float, int)` tuples (one per `self.agents[i]`)
- Stable index order: tuple at `[i]` corresponds to `agents[i]`, which maps to `_AGENT_TO_REGIME_BUCKET[i]`
- Existing `select_action()` (mean-average variant) unchanged for legacy callers

### Prerequisites applied from plans 02-03

Because this worktree was initialized at `b078445c` (before plans 01-03 were merged), the following prerequisite changes were also applied:

- `config.py`: `transformer_layers: int = 3` (was 4, FR-5.4)
- `rl/transformer_encoder.py`: `n_layers: int = 3` default (was 4, FR-5.4)
- `rl/sac_agent.py`: Full rewrite with `BetaActor` (FR-5.3), distinct seeds/hyperparameter perturbation (FR-5.1), `_perturb_cfg()` helper
- `backend/tests/rl/__init__.py`: Test package marker

## Notes for Plan 05 (Training Loop)

The training loop should call these two methods per step:
```python
# Per environment step:
agent_outputs = ensemble.select_action_per_agent(obs)       # list of 5 (entry, hold)
action = moe.blend(agent_outputs=agent_outputs, macro_score=score)  # MoEAction

# After RL update, log dominant regime:
log_regime(action.dominant_regime, action.weights)
```

The `action.weights` (`RegimeWeights`) contains `expansion`, `caution`, `crisis` floats useful for dashboard logging.

## Deviations from Plan

### Auto-applied prerequisite updates (Rule 3 - Blocking Issue)

**Found during:** Task 1 setup
**Issue:** Worktree was initialized at `b078445c` which predates merged plans 02-03. Files `rl/sac_agent.py`, `rl/transformer_encoder.py`, and `config.py` had old content (ContinuousActor, n_layers=4, transformer_layers=4) that would cause test failures.
**Fix:** Applied the same changes as plans 02-03 to bring worktree to the expected base state before implementing plan 04.
**Files modified:** `rl/sac_agent.py`, `rl/transformer_encoder.py`, `config.py`

## Known Stubs

None. All implemented functionality is fully wired. The `select_action_per_agent` method returns real agent outputs, not mocked data.

## Threat Flags

None. No new network endpoints or trust boundaries introduced.

## Self-Check

**Files verified present:**
- `rl/moe_controller.py`: contains `def blend`, `agent_outputs`, `_regime_weights_to_agent_weights`, `_AGENT_TO_REGIME_BUCKET`
- `rl/sac_agent.py`: contains `def select_action_per_agent`, `list[tuple[float, int]]`
- `backend/tests/rl/__init__.py`: created
- `backend/tests/rl/test_moe_controller.py`: contains `test_blend_all_five`, `test_five_agent_blend_shape`, `test_regime_weights_sum`
- `config.py`: `transformer_layers: int = 3`
- `rl/transformer_encoder.py`: `n_layers: int = 3`

**Acceptance criteria verified (grep counts):**
- `agent_outputs: list[tuple[float, int]]` in moe_controller.py: 1 (PASS)
- `def _regime_weights_to_agent_weights` in moe_controller.py: 1 (PASS)
- `_AGENT_TO_REGIME_BUCKET` in moe_controller.py: 2 (PASS, >= 2)
- `raw_entries: dict[Regime, float]` in moe_controller.py: 0 (PASS, old API removed)
- `class RegimeSpecialist` in moe_controller.py: 0 (PASS, legacy class removed)
- `_SPECIALISTS` in moe_controller.py: 0 (PASS)
- `if len(agent_outputs) != 5` in moe_controller.py: 1 (PASS)
- `def select_action_per_agent` in sac_agent.py: 1 (PASS)

**Staged files (git commits blocked by sandbox - orchestrator will commit on merge):**
- `A  backend/tests/rl/__init__.py`
- `A  backend/tests/rl/test_moe_controller.py`
- `M  config.py`
- `M  rl/moe_controller.py`
- `M  rl/sac_agent.py`
- `M  rl/transformer_encoder.py`

## Self-Check: PASSED
