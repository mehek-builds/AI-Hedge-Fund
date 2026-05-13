---
phase: 05-sac-ensemble-rl
plan: 02b
subsystem: rl
tags: [transformer, pretrain, eps-surprise, fr-5.4, earnings]
dependency_graph:
  requires: [05-02]
  provides: [rl/pretrain_transformer.py, rl/weights/transformer_pretrained.pt (runtime), rl/db_per.py (stub)]
  affects: [05-05 (SACEnsemble loads frozen encoder)]
tech_stack:
  added: []
  patterns: [EPS surprise regression, sliding window sequence, MSELoss pretrain, CLS token pooling]
key_files:
  created:
    - rl/pretrain_transformer.py
    - rl/db_per.py
    - backend/tests/rl/__init__.py
    - backend/tests/rl/test_transformer_encoder.py
    - rl/weights/.gitkeep
  modified:
    - rl/transformer_encoder.py
    - config.py
    - .gitignore
decisions:
  - "eps_surprise derived as eps_actual - eps_estimate in SQL (earnings_events has no eps_surprise column)"
  - "db_per.py created as minimal stub with get_engine; full implementation deferred to Plan 05-03"
  - "rl/weights/*.pt added to .gitignore: checkpoint is local-only dev artifact per threat model T-05-23"
  - "transformer n_layers default fixed 4->3 in both transformer_encoder.py and config.py (missed from 05-02 merge into this worktree)"
metrics:
  duration: ~15 minutes
  completed: 2026-05-13
  tasks_completed: 2
  files_changed: 8
---

# Phase 05 Plan 02b: Transformer Pre-training Script Summary

**One-liner:** Standalone EPS surprise regression pretrain for TransformerStateEncoder using earnings_events (eps_actual - eps_estimate derived; saves frozen-loadable checkpoint to rl/weights/transformer_pretrained.pt).

## What Was Built

### rl/pretrain_transformer.py (201 lines)

Public functions:
- `pretrain(database_url, n_epochs, batch_size, lr, output_path, seq_len, input_dim, min_quarters) -> Path`: trains encoder + linear head on next-quarter EPS surprise regression via MSELoss; saves encoder.state_dict() to checkpoint path; returns path.
- `_load_eps_series(engine) -> dict[str, list[float]]`: parameterized SQLAlchemy text() SELECT on earnings_events; derives eps_surprise = eps_actual - eps_estimate per row.
- `_build_windows(series, seq_len, input_dim, min_quarters) -> (X, y, n_tickers)`: sliding windows of 8 quarters, pads to input_dim=31 with zeros (dim 0 = eps_surprise).
- `_cli() -> int`: argparse CLI for `python -m rl.pretrain_transformer`.
- `_PretrainHead`: tiny nn.Linear(d_model, 1) head for regression during pretrain only.

Key behaviors:
- eps_surprise is DERIVED as eps_actual - eps_estimate. The earnings_events table has no eps_surprise column (RESEARCH.md A4 wording was misleading; resolved in this plan).
- Default output: rl/weights/transformer_pretrained.pt
- Graceful skip: if 0 tickers qualify (fewer than min_quarters=8 quarters of clean data), exits with code 2 and message "FR-5.4: insufficient earnings history..."
- No f-string SQL: all queries use sqlalchemy.text() with no string interpolation (T-05-21 mitigated).
- Encoder initialized with n_layers=3 (matches FR-5.4 and SACConfig.transformer_layers=3).

### rl/db_per.py (stub, 31 lines)

Provides `get_engine(database_url=None) -> Engine` for the pretrain script. Full implementation (upsert_transition, fetch_top_priority, update_priority_in_db) is delivered in Plan 05-03. This stub avoids an import error and aligns with the interface defined in the plan.

### backend/tests/rl/test_transformer_encoder.py

Created with:
- `test_layer_count`: SACConfig.transformer_layers == 3
- `test_encoder_config`: TransformerStateEncoder default d_model=64, n_layers=3
- `test_frozen_encoder`: freeze() sets all requires_grad=False
- `test_frozen_encoder_loads_weights` (FR-5.4 new): saves state_dict to temp .pt, loads via from_pretrained, asserts all params frozen AND sentinel weight matches saved value within 1e-6.

## Wiring Note for Plan 05-05 (SACEnsemble)

SACEnsemble.__init__ should:
```python
pretrained_path = Path("rl/weights/transformer_pretrained.pt")
if pretrained_path.exists():
    encoder = TransformerStateEncoder.from_pretrained(
        str(pretrained_path), input_dim=31, n_layers=3
    )
else:
    encoder = TransformerStateEncoder(input_dim=31, n_layers=3)
    encoder.freeze()
```
This allows the trainer to run before pretrain has been executed (fresh-init fallback), while using frozen pre-trained weights when available.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Missing dependency] Created rl/db_per.py stub**
- **Found during:** Task 2 (pretrain_transformer.py imports get_engine from rl.db_per)
- **Issue:** rl/db_per.py did not exist; plan 05-03 was supposed to create it but runs in a later wave
- **Fix:** Created minimal stub with get_engine() only; full implementation left to Plan 05-03
- **Files modified:** rl/db_per.py (new)

**2. [Rule 1 - Bug] Fixed transformer n_layers default 4->3 in both encoder and config**
- **Found during:** Task 1 setup (test_layer_count and test_encoder_config from dependency 05-02 were failing)
- **Issue:** The 05-02 merge commit (d34480fa) was not in this worktree branch; transformer_encoder.py still had n_layers=4, config.py still had transformer_layers=4
- **Fix:** Updated rl/transformer_encoder.py n_layers default 4->3; config.py SACConfig.transformer_layers 4->3
- **Files modified:** rl/transformer_encoder.py, config.py

**3. [Rule 2 - Security] Added rl/weights/*.pt to .gitignore**
- **Found during:** Task 2 (per threat model T-05-23: checkpoint is local-only, not committed)
- **Fix:** Added gitignore entry; created rl/weights/.gitkeep to preserve directory in git
- **Files modified:** .gitignore (new entry), rl/weights/.gitkeep (new)

**4. [Infrastructure] Created backend/tests/rl/__init__.py**
- **Found during:** Task 1 setup (directory did not exist)
- **Fix:** Created directory and __init__.py so pytest can discover test_transformer_encoder.py
- **Files modified:** backend/tests/rl/__init__.py (new)

## Known Stubs

- `rl/db_per.py`: Only implements `get_engine`. The functions `upsert_transition`, `fetch_top_priority`, and `update_priority_in_db` are NOT present. These are required by Plan 05-03 (PER buffer DB integration). The stub is intentional and Plan 05-03 will add the missing functions.

## Threat Flags

| Flag | File | Description |
|------|------|-------------|
| threat_flag: info_disclosure | rl/pretrain_transformer.py | Default DB URL `postgresql://pead:pead@localhost:5432/pead` in get_engine fallback is dev-only; prod reads DATABASE_URL_SYNC env var |

## Self-Check

### Created files exist:
- rl/pretrain_transformer.py: FOUND
- rl/db_per.py: FOUND
- backend/tests/rl/__init__.py: FOUND
- backend/tests/rl/test_transformer_encoder.py: FOUND
- rl/weights/.gitkeep: FOUND

### Acceptance criteria:
- `grep -c "def pretrain" rl/pretrain_transformer.py` = 1: PASS
- `grep -c "MSELoss" rl/pretrain_transformer.py` = 1: PASS
- `grep -c "FROM earnings_events" rl/pretrain_transformer.py` = 1: PASS
- `grep -c "eps_actual" rl/pretrain_transformer.py` >= 2: PASS (5)
- `grep -c "eps_estimate" rl/pretrain_transformer.py` >= 2: PASS (5)
- `grep -c "sys.exit(2)" rl/pretrain_transformer.py` = 1: PASS
- `grep -c "transformer_pretrained.pt" rl/pretrain_transformer.py` >= 1: PASS (2)
- `grep -c "n_layers=3" rl/pretrain_transformer.py` = 1: PASS
- No f-string SQL: PASS (0 matches)
- `grep -c "def test_frozen_encoder_loads_weights" backend/tests/rl/test_transformer_encoder.py` = 1: PASS
- `grep -c "from_pretrained" backend/tests/rl/test_transformer_encoder.py` >= 1: PASS (3)

### Note on commits:
All changes are staged in git (verified via `git status --short`). Git commit operations are blocked by the Bash hook in this execution environment. The orchestrator will need to commit these staged changes when merging this worktree branch.

## Self-Check: PASSED (files exist, criteria met; commits pending hook resolution)
