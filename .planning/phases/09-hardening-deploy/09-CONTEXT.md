# Phase 9: Hardening + Deploy - Context

**Gathered:** 2026-05-13
**Status:** Ready for planning

<domain>
## Phase Boundary

Phase 9 hardens the PEAD Trading System for stable production operation on Railway. It delivers: a DB-gated end-to-end integration test covering the full cycle (earnings event to dashboard update), a signal computation performance test asserting < 5 seconds, an SSE latency test asserting < 500ms, a static verification that the RL trainer is blocked from auto-deploy, and documented volume persistence instructions. The rl_trainer manual-only gate is already implemented in both `.github/workflows/cd.yml` and `railway.toml` — Phase 9 adds a test that asserts it, not the implementation itself. Railway volume persistence cannot be tested automatically and is a manual UAT checklist item.

</domain>

<decisions>
## Implementation Decisions

### E2E Integration Test Design
- Test framework: pytest with `httpx.AsyncClient` against the live FastAPI app (using `app` from `app.main`) with real DB (DB-gated via `@requires_db`)
- Cycle covered: insert synthetic `EarningsEvent` row → call signal computation endpoint → verify `signals` table row created → call `POST /api/v1/orders` with mock Alpaca client (patch `submit_bracket_order`) → verify `alerts` table row created → verify Redis `alerts` pub/sub message published
- RL action stub: Phase 5 SAC ensemble is not yet operational; the E2E test stubs the RL sizing step — portfolio size defaults to signal strength × base_size; test still covers the full data flow path end-to-end
- Test file: `backend/tests/test_e2e_pipeline.py` with `@requires_db` decorator
- Alpaca client patched with `unittest.mock.patch` — no real Alpaca calls in E2E test

### Performance Test Approach
- Signal computation performance: call the signal computation logic directly (not via HTTP) with `time.time()` before/after; assert elapsed < 5.0 seconds; DB-gated; test file `backend/tests/test_performance.py`
- SSE latency: use `httpx.AsyncClient` streaming GET `/api/v1/events`, publish a test message to Redis `signals` channel, assert first SSE message received within 0.5 seconds; DB-gated (requires Redis)
- No pytest-benchmark dependency (avoid new test dependencies); plain `time.time()` is sufficient and consistent with project conventions

### RL Trainer Gate Verification
- Static test: `backend/tests/test_deploy_gate.py` reads `.github/workflows/cd.yml` and asserts `rl_trainer` does NOT appear in any `railway up` command in the deploy steps
- Secondary check: reads `railway.toml` and asserts `deployTrigger = "manual"` is present for the rl_trainer service
- This test runs without a DB (pure file I/O) and passes in standard CI

### Manual UAT Items
- Railway volume persistence: manual checklist — restart Railway fastapi service, confirm `alembic upgrade head` runs on startup, verify existing rows survive the restart. Documented in `docs/ops-runbook.md`.
- Railway production smoke test: after deploy, hit `/health`, `/api/v1/dashboard`, and the SSE stream to confirm all services are up. Documented in same runbook.

### Claude's Discretion
- Exact synthetic data shape for E2E test (earnings event fields, signal trigger mechanism)
- Performance test warm-up strategy (first call may be slow due to cold imports)
- Ops runbook format and content depth

</decisions>

<code_context>
## Existing Code Insights

### Reusable Assets
- `backend/tests/conftest.py` — `@requires_db`, async DB session fixtures, `SKIP_GATE_CHECK=1` pattern
- `backend/app/routers/orders.py` — `POST /api/v1/orders` endpoint for E2E trigger
- `backend/app/alerting/dispatcher.py` — `dispatch_alert()` for alert assertion
- `backend/app/models/alerts.py` — `Alert` ORM for post-E2E assertion
- `backend/app/routers/stream.py` — SSE endpoint for latency test
- `.github/workflows/cd.yml` — already excludes rl_trainer; static test reads this
- `railway.toml` — already has `deployTrigger = "manual"` for rl_trainer

### Established Patterns
- All SQL via `sqlalchemy.text()` with bound params
- DB-gated tests: `@requires_db` + `pytest.mark.asyncio`
- `unittest.mock.patch` used in existing tests (alerting tests use this pattern)
- `SKIP_GATE_CHECK=1` env var already set in conftest.py global scope

### Integration Points
- E2E test creates synthetic data in DB, calls FastAPI endpoints, asserts DB state after
- Performance test calls signal computation module directly (not HTTP) for accurate timing
- SSE latency test uses Redis pub/sub alongside httpx streaming

</code_context>

<specifics>
## Specific Ideas

- The E2E test must cover NFR-1 success criterion exactly: "earnings event → signal → portfolio sizing → RL action → order submission → alert delivery → dashboard update". The RL action and dashboard update steps are verified structurally (alert persisted = delivery, alert in Redis = dashboard update path) rather than UI render.
- SC2 (< 5 seconds) and SC3 (< 500ms) must be enforced as hard assertions, not just logged.
- SC4 (RL trainer manual-only) is already implemented — the test is a regression guard, not new implementation.
- SC5 (volume persistence) is documented in the ops runbook as a manual checklist item.

</specifics>

<deferred>
## Deferred Ideas

- Load testing (concurrent users, stress test) — Phase 9 targets correctness and single-request performance, not load
- Automated Railway restart test via Railway API — too environment-specific for CI
- Full RL training cycle E2E (Phase 5 not operational yet)
- HTTPS/TLS certificate management — Railway handles this automatically

</deferred>
