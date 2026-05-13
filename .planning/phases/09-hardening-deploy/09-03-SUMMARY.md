---
phase: 09-hardening-deploy
plan: "03"
subsystem: testing-ops
tags: [deploy-gate, static-test, ops-runbook, nfr-4, nfr-5, railway]
dependency_graph:
  requires: []
  provides: [deploy-gate-test, ops-runbook]
  affects: [ci-pipeline, railway-ops]
tech_stack:
  added: []
  patterns: [static-file-read-test, ops-runbook-markdown]
key_files:
  created:
    - backend/tests/test_deploy_gate.py
    - docs/ops-runbook.md
  modified: []
key_decisions:
  - "Static deploy gate uses file I/O only: open() + string search, no DB, no imports beyond pathlib and pytest"
  - "Test skips gracefully with pytest.skip if cd.yml or railway.toml not found, rather than failing"
  - "Inline comment stripping (split on #) ensures commented-out examples of rl_trainer do not trigger false positives"
metrics:
  duration_minutes: 10
  completed_date: "2026-05-13"
  tasks_completed: 2
  files_created: 2
---

# Phase 9 Plan 03: Deploy Gate + Ops Runbook Summary

Static CI regression guard (NFR-4) that reads cd.yml and railway.toml to assert rl_trainer is excluded from auto-deploy, plus a manual UAT runbook for Railway volume persistence and production smoke tests (NFR-5).

## What Was Built

**Task 1: backend/tests/test_deploy_gate.py**

Two synchronous tests that run in CI without a database:

- `test_rl_trainer_excluded_from_cd_workflow`: reads `.github/workflows/cd.yml`, finds all lines containing `railway up`, strips inline comments, and asserts none of those lines contains `rl_trainer`. Skips gracefully if cd.yml is not found.
- `test_rl_trainer_deploy_trigger_is_manual`: reads `railway.toml` and asserts both `rl_trainer` and `deployTrigger = "manual"` are present in the file. Skips gracefully if railway.toml is not found.

Both tests resolve the repo root via `Path(__file__).parent.parent.parent` so they work from any working directory. Both tests passed locally in 0.00s with no DB required.

**Task 2: docs/ops-runbook.md**

277-line manual UAT runbook covering:
- Section 1: Railway volume persistence checklist (pre-restart row counts, trigger restart, watch Alembic logs, verify health, compare post-restart row counts, check volume mount if mismatch)
- Section 2: Production smoke test (curl commands for /health, /api/v1/dashboard, /api/v1/events SSE stream, /api/v1/signals, /api/v1/alerts)
- Section 3: RL trainer manual deploy instructions (CLI and dashboard paths, warning not to add to cd.yml)
- Section 4: Rollback procedure (Railway dashboard rollback, git revert, alembic downgrade -1)

## Verification Results

```
pytest tests/test_deploy_gate.py -v
  tests/test_deploy_gate.py::test_rl_trainer_excluded_from_cd_workflow PASSED
  tests/test_deploy_gate.py::test_rl_trainer_deploy_trigger_is_manual PASSED
  2 passed in 0.00s
```

All plan verification criteria met:
- `python3 -c "import ast; ast.parse(...)"` exits 0
- `grep -c "deployTrigger" test_deploy_gate.py` returns 7
- `grep -c "railway up" test_deploy_gate.py` returns 6
- `wc -l docs/ops-runbook.md` returns 277 (exceeds 60-line minimum)

## Commits

| Task | Commit | Files |
|------|--------|-------|
| T1: deploy gate tests | 211c03ef | backend/tests/test_deploy_gate.py |
| T2: ops runbook | 1b46e06d | docs/ops-runbook.md |

## Deviations from Plan

None - plan executed exactly as written.

The comment-stripping logic (`command_part = line.split("#")[0]`) was added as a minor
defensive measure to prevent false positives if cd.yml contains commented-out examples
of rl_trainer usage (which it does: the current cd.yml has a comment
`# rl_trainer is intentionally excluded` followed by example usage).
This is a Rule 1 auto-fix: the naive string search would fail on the existing cd.yml
comment block.

## Known Stubs

None.

## Threat Flags

None - no new network endpoints, auth paths, or trust boundaries introduced. The test
file is read-only and accesses only local files.

## Self-Check: PASSED

- backend/tests/test_deploy_gate.py: FOUND
- docs/ops-runbook.md: FOUND
- Commit 211c03ef: exists in git log
- Commit 1b46e06d: exists in git log
