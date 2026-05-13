# Roadmap: PEAD Trading System

## Overview

The system is built in a strict dependency order: stable infrastructure before data, clean data before signals, correct signals before portfolio controls, portfolio controls before RL training, a validated backtest before any order touches the paper account, and a functioning execution layer before the dashboard has anything real to display. Each phase produces a verifiable capability that the next phase depends on. The RL validation gate (Sharpe > 1.0) is a hard blocker between Phase 6 and Phase 7 — paper trading cannot start until the backtest passes.

## Phases

**Phase Numbering:**
- Integer phases (1, 2, 3): Planned milestone work
- Decimal phases (2.1, 2.2): Urgent insertions (marked with INSERTED)

Decimal phases appear between their surrounding integers in numeric order.

- [x] **Phase 1: Infrastructure & Data Foundation** - Docker Compose, TimescaleDB schema, Railway deployment, CI pipeline, point-in-time architecture (completed 2026-05-03)
- [ ] **Phase 2: Data Pipelines** - Prefect flows for prices, FRED macro, FF5 factors, earnings calendar, S&P 500 constituent history
- [x] **Phase 3: Signal Engine** - Market-implied EPS, earnings quality decomposition, three-axis composite, sector hurdles, naive baseline (completed 2026-05-03)
- [x] **Phase 4: Portfolio Architecture** (completed 2026-05-03) - Macro composite gate, ERP monitor, Mag-7 controls, completion portfolio optimizer
- [ ] **Phase 5: SAC Ensemble RL** - 5-agent SAC with PER, MoE meta-controller, Transformer encoder, diversity monitoring
- [ ] **Phase 6: Backtest Engine + Validation Gate** - 2018-2023 point-in-time replay, full stats, Sharpe > 1.0 go/no-go gate
- [x] **Phase 7: Alpaca Execution + Alerting** - Bracket orders, position sync, orphan detection, SendGrid+Slack alerts, 9 event types (completed 2026-05-13)
- [ ] **Phase 8: Frontend Dashboard** - Next.js 14 dark dashboard, SSE real-time, all 8 views
- [ ] **Phase 9: Hardening + Deploy** - End-to-end integration tests, Railway production config, performance validation, NFR verification

## Phase Details

### Phase 1: Infrastructure & Data Foundation
**Goal**: The complete runtime environment exists, all services connect, the database schema is in place with point-in-time semantics, and CI/CD can deploy without manual intervention
**Depends on**: Nothing (first phase)
**Requirements**: FR-1.1, FR-1.2, FR-1.3, FR-1.4, FR-1.5
**Success Criteria** (what must be TRUE):
  1. `docker compose up` starts all 6 services (FastAPI, Next.js, Celery, PostgreSQL+TimescaleDB, Redis, Prefect) with no errors and health checks pass
  2. All 6 TimescaleDB hypertables exist (`price_bars`, `earnings_events`, `signals`, `rl_transitions`, `macro_indicators`, `portfolio_positions`) and accept writes
  3. Railway deployment runs with a persistent volume; a schema migration survives a Railway service restart without data loss
  4. GitHub Actions CI runs lint, test, and Docker build on a PR; a merge to main triggers auto-deploy to Railway
  5. All historical records written to the DB include `ingestion_timestamp`; a test query using `as_of` filtering returns only records visible at that timestamp
**Plans:** 3/3 plans complete
- [x] 01-01-PLAN.md — Docker Compose stack with 6 services, FastAPI/Next.js/Celery skeletons (FR-1.1)
- [x] 01-02-PLAN.md — Alembic + TimescaleDB hypertables migration with point-in-time as_of filter (FR-1.2, FR-1.5)
- [x] 01-03-PLAN.md — Railway deploy + GitHub Actions CI/CD with rl_trainer exclusion (FR-1.3, FR-1.4)

### Phase 2: Data Pipelines
**Goal**: All upstream data sources flow into the database on schedule; the system has clean, point-in-time price, macro, factor, and earnings data ready for signal computation
**Depends on**: Phase 1
**Requirements**: FR-2.1, FR-2.2, FR-2.3
**Success Criteria** (what must be TRUE):
  1. Prefect dashboard shows 6 scheduled flows; all run successfully on their cron schedules without manual intervention
  2. `price_bars` table contains daily OHLCV for all current S&P 500 members with no gaps in the last 30 trading days
  3. `macro_indicators` table contains the latest vintage values for all 6 FRED series (yield curve, Sahm, LEI, ISM, HYG/LQD, JPY/AUD)
  4. Ken French FF5 factor data is present in the DB and queryable by date
  5. `earnings_events` table contains FMP actuals (EPS, revenue, operating income, share count, guidance direction) for the last 2 earnings seasons
  6. S&P 500 constituent history table exists and a point-in-time query for any date between 2018-2023 returns the correct membership (survivorship bias test passes)
**Plans:** 5 plans
- [x] 02-01-PLAN.md — Phase 2 schema migrations (sp500_constituents, ff5_factors) + shared flow base utilities (FR-2.1)
- [x] 02-02-PLAN.md — Alpaca daily OHLCV ingestion flow for S&P 500 universe (FR-2.1, FR-2.2)
- [x] 02-03-PLAN.md — FRED 6-series macro flow + Ken French FF5 weekly flow (FR-2.2, FR-2.3)
- [x] 02-04-PLAN.md — FMP earnings flow + Wikipedia S&P 500 constituent history + point-in-time query (FR-2.1, FR-2.3)
- [x] 02-05-PLAN.md — HYG/LQD derived spread + integration test + deploy-all script + Prefect dashboard verification (FR-2.1, FR-2.2, FR-2.3)

### Phase 3: Signal Engine
**Goal**: Given a new earnings event, the system computes a market-implied EPS signal, earnings quality score, three-axis composite, and a naive baseline position size — all within 5 seconds
**Depends on**: Phase 2
**Requirements**: FR-3.1, FR-3.2, FR-3.3, FR-3.4, FR-3.5, FR-3.6, FR-3.7
**Success Criteria** (what must be TRUE):
  1. For any ticker with a completed earnings event, the system produces a market-implied EPS value computed as price ÷ sector median forward P/E (not analyst consensus)
  2. A quality decomposition score (0–100) is generated with all four components visible (revenue surprise, margin expansion, share count discipline, guidance direction)
  3. Sector hurdle rates are applied; signals below the sector threshold are suppressed and logged as such
  4. ROIC > WACC filter is applied to tech/biotech names; filter decisions are logged
  5. Three-axis composite (valuation × quality × momentum) is computed and persisted to the `signals` table
  6. Naive baseline produces a fixed 2% NAV position size for any signal-aligned name; this value is stored alongside the signal and used as the IR denominator
  7. End-to-end signal computation for one earnings event completes in under 5 seconds
**Plans:** 3 plans
- [x] 03-01-PLAN.md — Sector map + market-implied EPS + 4-component quality scorer (FR-3.1, FR-3.2)
- [x] 03-02-PLAN.md — Momentum + composite + sector-hurdle/ROIC-WACC filters + signal writer + pipeline (FR-3.3, FR-3.4, FR-3.5, FR-3.6)
- [x] 03-03-PLAN.md — Celery task wrapper + DB-gated integration tests + <5s performance benchmark (FR-3.7)

### Phase 4: Portfolio Architecture
**Goal**: Every signal-driven position size is gated through macro regime controls, ERP compression caps, Mag-7 concentration limits, and a completion portfolio that neutralizes unintended factor tilts
**Depends on**: Phase 3
**Requirements**: FR-4.1, FR-4.2, FR-4.3, FR-4.4, FR-4.5, FR-4.6
**Success Criteria** (what must be TRUE):
  1. Macro composite score (0 to −6) is computed from all 6 components (yield curve, Sahm Rule, LEI, ISM PMI, HYG/LQD credit spreads, JPY/AUD carry) and stored in `macro_indicators`
  2. Sizing multiplier is correctly applied: 1.0× for scores 0 to −1, 0.6–0.7× for −2 to −3, 0.2–0.3× for −4 to −6; a unit test covering all three bands passes
  3. When E/P < real TIPS 10Y yield, the global ERP cap of 0.8× is applied to all position sizes
  4. Any signal producing a position > 3% NAV in a Mag-7 name is capped to 3%; the cap is logged as a constraint event
  5. Completion portfolio allocates ~23% NAV to IVE/IYR; scipy SLSQP optimizer produces weights that achieve target FF3 betas (Mkt-Rf ≈ 0.985, SMB ≈ −0.155, HML ≈ +0.025) within tolerance
  6. An 8% stop-loss hard limit is enforced independently of RL sizing recommendations; a unit test confirms stop triggers at exactly 8% drawdown from entry
**Plans:** 3 plans
- [x] 04-01-PLAN.md — Macro composite scorer + sizing multiplier + Mag-7 cap + ERP cap + 8% stop-loss (FR-4.1, FR-4.2, FR-4.3, FR-4.4, FR-4.6)
- [x] 04-02-PLAN.md — Completion portfolio SLSQP optimizer + sizing pipeline orchestrator (FR-4.5)
- [x] 04-03-PLAN.md — Celery task wrapper + macro_loader (DB read) + DB-gated integration tests (FR-4.1..FR-4.6)

### Phase 5: SAC Ensemble RL
**Goal**: Five independent SAC agents are training on historical transitions, producing diverse sizing outputs that a MoE meta-controller blends by macro regime — with diversity monitoring to detect and alert on ensemble collapse
**Depends on**: Phase 4
**Requirements**: FR-5.1, FR-5.2, FR-5.3, FR-5.4, FR-5.5, FR-5.6, FR-5.7, FR-5.8, FR-5.9
**Success Criteria** (what must be TRUE):
  1. 5 SAC agents initialize with distinct random seeds and hyperparameter perturbations (±30%); no two agents share identical network weights at initialization
  2. Experience replay transitions are stored in and sampled from the PostgreSQL `rl_transitions` hypertable (not Redis); prioritized sampling returns higher-priority transitions more frequently
  3. Each agent outputs a continuous position size in [0,1] via Beta distribution; macro multiplier is applied post-RL as a deterministic override and does not backpropagate
  4. Transformer encoder (d_model=64, 3 layers, 4 heads, 8-quarter input) is pre-trained on next-quarter EPS surprise regression and loads frozen weights in v1.0
  5. MoE meta-controller classifies the current macro state into one of 3 regimes (expansion/caution/crisis) and produces a weighted blend of the 5 agent outputs
  6. Pairwise cosine similarity between agent action distributions is computed after each training epoch; a similarity > 0.9 triggers an `rl_diversity_alert` event
  7. RL trainer Railway service requires manual deploy; checkpoints are written to PostgreSQL every 1,000 training steps
**Plans:** 6 plans
- [ ] 05-01-PLAN.md — Wave 0 test stubs + Alembic 0004 (rl_checkpoints, rl_diversity_alerts) (FR-5.1..FR-5.7 scaffolding)
- [ ] 05-02-PLAN.md — SAC core: BetaActor + distinct seeds/±30% perturbations + transformer 4→3 layers (FR-5.1, FR-5.3, FR-5.4)
- [ ] 05-03-PLAN.md — DB-backed PER buffer (push_to_db + hydrate_from_db, rl/db_per.py adapter) (FR-5.2)
- [ ] 05-04-PLAN.md — MoE redesign: blend all 5 agents via 0,1→expansion / 2,3→caution / 4→crisis projection (FR-5.5)
- [ ] 05-05-PLAN.md — Diversity monitor + worker/flows/rl_trainer.py with 1000-step checkpoint loop (FR-5.6, FR-5.7)
- [ ] 05-06-PLAN.md — DB-gated integration tests + deploy-gate static tests + human Phase 5 sign-off (FR-5.1..FR-5.7)


### Phase 6: Backtest Engine + Validation Gate
**Goal**: A 2018–2023 point-in-time replay runs using production signal and RL code, produces full performance statistics, and either passes the Sharpe > 1.0 gate (unblocking paper trading) or fails it (blocking Phase 7)
**Depends on**: Phase 5
**Requirements**: FR-6.1, FR-6.2, FR-6.3, FR-6.4, FR-6.5, FR-6.6
**Success Criteria** (what must be TRUE):
  1. Backtest replay uses only data with `ingestion_timestamp` ≤ `as_of` date for every query; a deliberately injected future data point is rejected by the filter
  2. Backtest imports and calls the production signal engine and SAC ensemble — no parallel backtest-only implementations exist
  3. Full statistics are computed and persisted: Sharpe ratio, max drawdown, IR vs. naive baseline, Calmar ratio, monthly returns breakdown
  4. Go/no-go gate is enforced programmatically: a `backtest_gate_pass` or `backtest_gate_fail` alert fires, and Phase 7 execution cannot proceed if gate fails
  5. Ex-2020 stress test runs as a separate backtest slice; Sharpe > 0.8 on the ex-2020 period is reported
  6. Backtest results are accessible in the `backtest_runs` table and visible in the dashboard Backtest Explorer view
**Plans**: TBD

### Phase 7: Alpaca Execution + Alerting
**Goal**: Paper trades execute via bracket orders, positions stay in sync with Alpaca state, orphaned orders are detected and cancelled, and all system events are delivered via SendGrid and Slack with rate limiting
**Depends on**: Phase 6 (Sharpe > 1.0 gate must pass)
**Requirements**: FR-7.1, FR-7.2, FR-7.3, FR-7.4, FR-7.5, FR-7.6, FR-8.1, FR-8.2, FR-8.3, FR-8.4
**Success Criteria** (what must be TRUE):
  1. A signal-triggered order submits a bracket order (limit entry + stop-loss leg + take-profit ceiling) via `alpaca-py` and the order appears in the Alpaca paper account
  2. On service startup, the positions table is reconciled with Alpaca live state; any discrepancy between DB and Alpaca is logged and resolved
  3. The orphan detector identifies any open exit order with no corresponding position and cancels it, firing an alert
  4. A SendGrid email and Slack webhook message are delivered for each of the 9 event types (signal_generated, order_submitted, order_filled, stop_triggered, thesis_broken, macro_regime_change, backtest_gate_pass, backtest_gate_fail, rl_diversity_alert)
  5. Rate limiting prevents more than 3 alerts per event type per hour; a burst of 10 same-type events in 5 minutes results in exactly 3 deliveries
  6. All alerts are persisted to PostgreSQL and visible in the dashboard Alerting view
  7. Short-side feature flag (`ENABLE_SHORT_SIDE`) exists in config and defaults to false; short orders are not placed when flag is off
**Plans:** 4/4 plans complete
- [x] 07-01-PLAN.md — Alembic 0007_alerts migration, Alert ORM model, Settings extensions, sendgrid dependency, Wave 0 test stubs
- [x] 07-02-PLAN.md — execution/ module (broker, position_sync, orphan_detector), POST /api/v1/orders router, Celery beat task, startup gate check
- [x] 07-03-PLAN.md — alerting/ module (dispatcher, rate_limiter, templates), all alerting tests
- [x] 07-04-PLAN.md — Wire dispatch_alert into orders router and gate alert, E2E integration checkpoint
**UI hint**: yes

### Phase 8: Frontend Dashboard
**Goal**: All system state — positions, signals, RL performance, macro conditions, backtest results, and alerts — is visible in a real-time dark-theme dashboard with Server-Sent Events updates under 500ms latency
**Depends on**: Phase 7
**Requirements**: FR-9.1, FR-9.2, FR-9.3, FR-9.4
**Success Criteria** (what must be TRUE):
  1. All 8 views render without errors in the Next.js 14 App Router with dark theme (#0A1628 bg, #2471A3 primary), Inter font, and JetBrains Mono for numeric fields
  2. SSE connection from FastAPI `StreamingResponse` → Redis pub/sub → Next.js `useEffect` delivers live position and signal updates; latency from event to dashboard update is under 500ms
  3. Dashboard view shows current NAV, daily P&L, active positions count, macro gate status, and last 5 alerts — all sourced from live data
  4. Signal Feed shows the most recent 20 earnings events with EPS gap, quality score, and three-axis composite per ticker
  5. Position Manager shows open positions with entry price, stop level, target, unrealized P&L, and thesis status (INTACT / MONITOR / BROKEN)
  6. RL Console shows per-agent reward curves and current MoE regime weights (reflecting live macro state)
  7. Backtest Explorer lets the user select a backtest run and view Sharpe/drawdown/IR stats alongside monthly returns heatmap
  8. Settings view exposes feature flags (short-side toggle), alert thresholds, and sizing parameters; changes persist and take effect without service restart
**Plans**: TBD
**UI hint**: yes

### Phase 9: Hardening + Deploy
**Goal**: The system runs reliably end-to-end in the Railway production environment: all integration tests pass, performance targets are met, and the deployment is stable under normal daily operating conditions
**Depends on**: Phase 8
**Requirements**: NFR-1, NFR-2, NFR-3, NFR-4, NFR-5
**Success Criteria** (what must be TRUE):
  1. An end-to-end integration test simulates a full cycle (earnings event → signal → portfolio sizing → RL action → order submission → alert delivery → dashboard update) and passes
  2. Signal computation for a single earnings event completes in under 5 seconds measured in the Railway environment
  3. Dashboard SSE latency (event to UI update) is under 500ms measured under normal operating load
  4. RL trainer is confirmed on manual-deploy-only; it cannot be triggered by a push to main
  5. Railway persistent volume survives a forced service restart with all schema and data intact
**Plans**: TBD

## Progress

**Execution Order:**
Phases execute in numeric order: 1 → 2 → 3 → 4 → 5 → 6 → 7 → 8 → 9

**Critical gate:** Phase 6 must produce Sharpe > 1.0 before Phase 7 begins.

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Infrastructure & Data Foundation | 3/3 | Complete | 2026-05-03 |
| 2. Data Pipelines | 0/5 | Not started | - |
| 3. Signal Engine | 0/TBD | Not started | - |
| 4. Portfolio Architecture | 0/3 | Not started | - |
| 5. SAC Ensemble RL | 0/6 | Not started | - |
| 6. Backtest Engine + Validation Gate | 0/TBD | Not started | - |
| 7. Alpaca Execution + Alerting | 4/4 | Complete   | 2026-05-13 |
| 8. Frontend Dashboard | 0/TBD | Not started | - |
| 9. Hardening + Deploy | 0/TBD | Not started | - |
