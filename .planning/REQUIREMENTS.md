# PEAD Trading System — Requirements

## Scope Statement

Single-user autonomous paper trading platform that ingests S&P 500 earnings events, computes PEAD signals enhanced by earnings quality decomposition, applies macro regime controls and portfolio architecture, executes trades via Alpaca paper API, and continuously improves via SAC ensemble RL — all surfaced through a real-time Next.js dashboard.

**Core validation gate:** RL engine must produce positive Information Ratio vs. naive fixed-size baseline. Backtest Sharpe > 1.0 required before paper go-live.

---

## Functional Requirements

### FR-1: Infrastructure
- **FR-1.1** Docker Compose with 6 services: FastAPI, Next.js, Celery worker, PostgreSQL+TimescaleDB, Redis, Prefect server
- **FR-1.2** TimescaleDB hypertables for: `price_bars`, `earnings_events`, `signals`, `rl_transitions`, `macro_indicators`, `portfolio_positions`
- **FR-1.3** Railway.app deployment with persistent volume attached before schema creation (ephemeral filesystem risk)
- **FR-1.4** GitHub Actions CI: lint, test, Docker build on PR; auto-deploy main to Railway (RL trainer service on manual deploy only)
- **FR-1.5** Point-in-time data architecture: all historical records tagged with `ingestion_timestamp`; no retroactive overwrites

### FR-2: Data Pipelines
- **FR-2.1** Prefect 2.x flows (cron-based, not interval-based) for:
  - Daily price ingest via Alpaca historical bars API
  - Daily FRED macro series (ALFRED vintage API for revised values)
  - Quarterly Ken French FF5 factor library download
  - Earnings calendar poll (FMP, 7-day rolling window)
  - Signal computation triggered on new earnings event (event-driven sub-flow)
  - Quarterly completion portfolio reoptimize (or when SSD > 0.005)
- **FR-2.2** S&P 500 constituent membership as point-in-time table (prevents survivorship bias in backtest)
- **FR-2.3** FMP earnings data: EPS actual/estimate, revenue, operating income, share count, guidance direction per quarter per ticker

### FR-3: Signal Engine
- **FR-3.1** Market-implied EPS = current price ÷ sector median forward P/E (NOT analyst consensus)
- **FR-3.2** EPS gap = (market-implied EPS - actual EPS) / |actual EPS| × 100
- **FR-3.3** Earnings quality decomposition score (0–100):
  - Revenue surprise component (actual vs. expected QoQ growth)
  - Margin expansion component (operating margin delta)
  - Share count discipline (dilution/buyback direction)
  - Guidance direction proxy (analyst forward estimate revision, 5-day post-announcement)
- **FR-3.4** Sector hurdle rates: minimum EPS gap threshold per GICS sector
- **FR-3.5** Intangible/ROIC filter: ROIC > WACC for tech/biotech names (via Compustat or FMP balance sheet)
- **FR-3.6** Three-axis composite: valuation (EPS gap) × operating performance (quality score) × momentum (1/3-month price momentum)
- **FR-3.7** Naïve baseline: fixed 2% NAV per signal-aligned name, no RL sizing — used to compute IR denominator

### FR-4: Portfolio Architecture
- **FR-4.1** Macro composite score (0 to −6) from: yield curve, Sahm Rule, LEI, ISM PMI, HYG/LQD credit spreads, JPY/AUD carry
- **FR-4.2** Sizing multiplier: 1.0× (0 to −1), 0.6–0.7× (−2 to −3), 0.2–0.3× (−4 to −6)
- **FR-4.3** ERP compression cap: 0.8× global multiplier when E/P < real TIPS 10Y yield
- **FR-4.4** Mag-7 concentration control: max 3% NAV per Mag-7 name (AAPL, MSFT, NVDA, GOOGL, AMZN, META, TSLA)
- **FR-4.5** Completion portfolio: ~23% NAV in IVE/IYR to neutralize FF3 factor drift; scipy SLSQP optimizer targeting S&P 500 betas (Mkt-Rf=0.985, SMB=−0.155, HML=+0.025)
- **FR-4.6** Hard stop-loss: 8% from entry (long); stop triggers independent of RL agent opinion

### FR-5: SAC Ensemble RL
- **FR-5.1** 5 independent SAC agents (Stable Baselines 3, PyTorch backend) with per-agent hyperparameter perturbation (±30% of defaults) and separate random seeds — prevents ensemble collapse
- **FR-5.2** Prioritized Experience Replay stored in PostgreSQL `rl_transitions` hypertable (not Redis — memory ceiling exceeded)
- **FR-5.3** Action space: continuous [0,1] position sizing via Beta distribution parameterization; macro multiplier applied post-RL as deterministic override
- **FR-5.4** State space: EPS gap, quality score, momentum components, macro composite, VIX regime, time-to-next-earnings, current position size, unrealized P&L
- **FR-5.5** Reward: FF5 factor-adjusted alpha / volatility; 1.5× asymmetric loss weighting; tail penalty for single-day drawdown > 2%
- **FR-5.6** Mixture-of-Experts meta-controller: 8-dim macro state → 3-regime gating (expansion/caution/crisis) → weighted blend of 5 agent outputs; pre-trained as regime classifier before RL training
- **FR-5.7** Transformer state encoder: d_model=64, 3 layers, 4 heads, 8-quarter sequence; pre-training objective = next-quarter EPS surprise regression; frozen in v1.0
- **FR-5.8** Ensemble diversity monitoring: per-agent IR tracked; alert if pairwise cosine similarity > 0.9
- **FR-5.9** RL trainer as isolated Railway service on manual deploy only; checkpoint every 1,000 steps to PostgreSQL

### FR-6: Backtest Engine
- **FR-6.1** 2018–2023 replay using point-in-time data only (strict `as_of` filtering for all historical queries)
- **FR-6.2** Reuses production signal engine and SAC ensemble code — no separate backtest implementations
- **FR-6.3** Full statistics: Sharpe ratio, max drawdown, IR vs. naïve baseline, Calmar ratio, monthly returns heatmap
- **FR-6.4** Go/no-go gate: Sharpe > 1.0 required before paper go-live
- **FR-6.5** Stress tests: ex-2020 Sharpe > 0.8; rolling 12-month Sharpe stability
- **FR-6.6** Results persisted to `backtest_runs` table; accessible via dashboard Backtest Explorer view

### FR-7: Alpaca Integration
- **FR-7.1** `alpaca-py` SDK (not deprecated `alpaca-trade-api`)
- **FR-7.2** Bracket orders: limit entry + stop-loss leg + nominal take-profit ceiling (per Shepherd framework: signal-driven exits, hard stop as tail protection)
- **FR-7.3** Bracket orphan detector: any open exit order with no corresponding position → cancel and alert
- **FR-7.4** Position sync on service startup: reconcile PostgreSQL positions table with Alpaca live state
- **FR-7.5** Short-side PEAD behind `ENABLE_SHORT_SIDE` feature flag; disabled by default in v1.0
- **FR-7.6** Order rate limiting: respect Alpaca paper account limits (≤ 200 req/min)

### FR-8: Alerting
- **FR-8.1** SendGrid email + Slack webhook dual delivery
- **FR-8.2** 9 event types: signal_generated, order_submitted, order_filled, stop_triggered, thesis_broken, macro_regime_change, backtest_gate_pass, backtest_gate_fail, rl_diversity_alert
- **FR-8.3** Rate limiting: max 3 alerts per event type per hour (prevents alert storms)
- **FR-8.4** Alert log persisted to PostgreSQL for dashboard display

### FR-9: Frontend Dashboard
- **FR-9.1** Next.js 14 App Router, TypeScript, dark theme (#0A1628 bg, #2471A3 primary, #148F77 positive, #C0392B negative), Inter font, JetBrains Mono for numbers
- **FR-9.2** Real-time updates via Server-Sent Events (SSE) from FastAPI `StreamingResponse` → Redis pub/sub fan-out; NOT WebSocket (SSE survives Railway proxy)
- **FR-9.3** 8 views:
  1. **Dashboard** — NAV, daily P&L, active positions, macro gate status, recent alerts
  2. **Signal Feed** — live earnings events, EPS gaps, quality scores, three-axis composite per ticker
  3. **Position Manager** — open positions, entry/stop/target, unrealized P&L, thesis status (INTACT/MONITOR/BROKEN)
  4. **RL Console** — per-agent reward curves, diversity metrics, MoE regime weights, action distribution
  5. **Macro/Architecture** — macro composite score components, ERP monitor, completion portfolio factor chart
  6. **Backtest Explorer** — run selector, Sharpe/drawdown/IR stats, monthly heatmap, naïve comparison
  7. **Alerting** — alert log, delivery status, rate limit status per event type
  8. **Settings** — API keys, feature flags (short-side), alert thresholds, sizing parameters
- **FR-9.4** All interactive components are Client Components (`'use client'`); SSE subscription in useEffect

---

## Non-Functional Requirements

- **NFR-1: Backtest correctness** — all historical queries use point-in-time data with strict `as_of`; look-ahead bias produces false Sharpe > 1.0 gate pass, which is the highest-severity defect class
- **NFR-2: Deployment safety** — RL trainer on manual deploy only; Railway persistent volume mounted before any schema creation
- **NFR-3: Data cost** — FMP ~$25/mo; all other sources free. No additional data vendors in v1.0.
- **NFR-4: Performance** — signal computation < 5s per earnings event; dashboard SSE latency < 500ms
- **NFR-5: Single-user** — no auth layer required in v1.0; not exposed to public internet in Railway deployment

---

## Out of Scope (v1.0)

| Feature | Reason | Version |
|---------|--------|---------|
| Live brokerage execution | Paper-first; credential swap only for v2.0 | v2.0 |
| Short-side PEAD | Feature flag exists; disabled by default; no test coverage | v2.0 |
| Mobile-responsive frontend | Web-first | v3.0 |
| Multi-user / auth layer | Single-user internal | v3.0 |
| Options overlay | Not in PRD scope | v3.0 |
| International equities | US S&P 500 only | Future |
| Prefect Cloud | Self-hosted on Railway sufficient | Future |
| GPU for RL training | Railway CPU sufficient for S&P 500 scope | v2.0 |

---

## Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| FR-1.1 | Phase 1 | Pending |
| FR-1.2 | Phase 1 | Pending |
| FR-1.3 | Phase 1 | Pending |
| FR-1.4 | Phase 1 | Pending |
| FR-1.5 | Phase 1 | Pending |
| FR-2.1 | Phase 2 | Pending |
| FR-2.2 | Phase 2 | Pending |
| FR-2.3 | Phase 2 | Pending |
| FR-3.1 | Phase 3 | Pending |
| FR-3.2 | Phase 3 | Pending |
| FR-3.3 | Phase 3 | Pending |
| FR-3.4 | Phase 3 | Pending |
| FR-3.5 | Phase 3 | Pending |
| FR-3.6 | Phase 3 | Pending |
| FR-3.7 | Phase 3 | Pending |
| FR-4.1 | Phase 4 | Pending |
| FR-4.2 | Phase 4 | Pending |
| FR-4.3 | Phase 4 | Pending |
| FR-4.4 | Phase 4 | Pending |
| FR-4.5 | Phase 4 | Pending |
| FR-4.6 | Phase 4 | Pending |
| FR-5.1 | Phase 5 | Pending |
| FR-5.2 | Phase 5 | Pending |
| FR-5.3 | Phase 5 | Pending |
| FR-5.4 | Phase 5 | Pending |
| FR-5.5 | Phase 5 | Pending |
| FR-5.6 | Phase 5 | Pending |
| FR-5.7 | Phase 5 | Pending |
| FR-5.8 | Phase 5 | Pending |
| FR-5.9 | Phase 5 | Pending |
| FR-6.1 | Phase 6 | Pending |
| FR-6.2 | Phase 6 | Pending |
| FR-6.3 | Phase 6 | Pending |
| FR-6.4 | Phase 6 | Pending |
| FR-6.5 | Phase 6 | Pending |
| FR-6.6 | Phase 6 | Pending |
| FR-7.1 | Phase 7 | Pending |
| FR-7.2 | Phase 7 | Pending |
| FR-7.3 | Phase 7 | Pending |
| FR-7.4 | Phase 7 | Pending |
| FR-7.5 | Phase 7 | Pending |
| FR-7.6 | Phase 7 | Pending |
| FR-8.1 | Phase 7 | Pending |
| FR-8.2 | Phase 7 | Pending |
| FR-8.3 | Phase 7 | Pending |
| FR-8.4 | Phase 7 | Pending |
| FR-9.1 | Phase 8 | Pending |
| FR-9.2 | Phase 8 | Pending |
| FR-9.3 | Phase 8 | Pending |
| FR-9.4 | Phase 8 | Pending |
| NFR-1 | Phase 9 | Pending |
| NFR-2 | Phase 9 | Pending |
| NFR-3 | Phase 9 | Pending |
| NFR-4 | Phase 9 | Pending |
| NFR-5 | Phase 9 | Pending |

---

*Last updated: 2026-05-02 after roadmap creation*
