# PEAD Trading System

## What This Is

An autonomous, single-user trading platform that ingests S&P 500 earnings events, computes Post-Earnings Announcement Drift (PEAD) signals enhanced by earnings quality decomposition, applies macro regime and portfolio architecture controls, executes trades via Alpaca (paper v1.0 → live v2.0), and continuously improves through a Soft Actor-Critic ensemble with a Mixture-of-Experts regime conditioner — all surfaced through a real-time dashboard.

## Core Value

The RL engine must earn a positive Information Ratio vs. the naive fixed-size baseline — if the SAC ensemble doesn't add value over a simple signal-threshold strategy, the system has no reason to exist.

## Requirements

### Validated

(None yet — ship to validate)

### Active

- [ ] Infrastructure: Docker Compose (6 services), PostgreSQL + TimescaleDB, Redis, Railway deployment, GitHub Actions CI
- [ ] Data pipelines: Prefect flows for prices (Alpaca), FRED macro series, FF5 factors (Ken French), earnings calendar (FMP)
- [ ] Signal engine: market-implied EPS signal, earnings quality decomposition (revenue/margin/share count/guidance), sector hurdle rates, intangible/ROIC filters
- [ ] Portfolio architecture: macro composite score, ERP monitor, growth/value spread, Mag 7 controls, completion portfolio optimizer
- [ ] SAC ensemble RL: 5 agents, Prioritized Experience Replay, Mixture-of-Experts meta-controller, Transformer state encoder pre-training
- [ ] Backtest engine: 2018–2023 replay, full stats (Sharpe, max drawdown, IR vs. naive), validates Sharpe > 1.0 before go-live
- [ ] Alpaca integration: order execution, stop monitoring, position sync, short-side feature flag
- [ ] Alerting: SendGrid email + Slack webhook, 9 event types, rate limiting
- [ ] Frontend: Next.js 14 dark dashboard, 8 views (Dashboard, Signal Feed, Position Manager, RL Console, Macro/Architecture, Backtest Explorer, Alerting, Settings)

### Out of Scope (v1.0)

- Live brokerage execution — paper trading only; live is v2.0
- Short-side PEAD — designed and specced but behind feature flag, disabled by default
- Mobile-responsive frontend — web-first
- Multi-user support — single-user internal system
- Options overlay — v3.0
- International equities — US S&P 500 only

## Context

- **Brokerage**: Alpaca paper trading API (identical to live — credential swap only for v2.0)
- **RL Algorithm**: SAC Ensemble (5 agents) + Mixture-of-Experts meta-controller
- **Signal Basis**: Market-Implied EPS (price ÷ sector median forward P/E) — not analyst consensus
- **Universe**: S&P 500 constituents
- **Data sources**: Alpaca (prices), FRED (macro), Ken French library (FF5 factors), FMP (~$25/mo, earnings actuals + quality), Compustat/WRDS (ROIC, intangibles), yfinance (VIX, ETF P/E)
- **Deployment**: Docker Compose locally, Railway.app for hosted (~$30/mo total)
- **PRD**: `/Users/Mehek1/Documents/Second Brain/building/PEAD-Trading-System-PRD-v4.docx` — full spec including DB schema, API endpoints, RL architecture, signal engine formulas
- **Existing vault docs**: `building/raw/usif-shepherd-investment-philosophy.md`, `usif-shepherd-sizing-framework.md`, `usif-shepherd-monitoring-and-changing.md` — Shepherd PEAD framework underpinning the signal design
- **Pre-market briefing script**: `building/scripts/pre-market-briefing.py` — manual paper trading already running on Alpaca paper account (PA37Q36MZCKN, $100k NAV)
- **Alpaca keys**: `.env` in building dir — paper account active, orders placed

## Constraints

- **Tech stack**: Next.js 14 + TypeScript, FastAPI, Celery + Redis, PostgreSQL + TimescaleDB, PyTorch (SAC + Transformer), Prefect 2.0 — defined in PRD, not negotiable
- **Design system**: Dark theme (#0A1628 bg, #2471A3 primary, #148F77 positive, #C0392B negative), Inter font, JetBrains Mono for numbers — defined in PRD
- **RL validation gate**: Backtest Sharpe > 1.0 required before paper trading go-live; rolling alpha t-stat > 2.0 required before live capital
- **Data cost**: FMP API ~$25/mo; all other sources free
- **Paper-first**: No live capital in v1.0 — Alpaca paper only

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| SAC ensemble (5 agents) over PPO | Off-policy sample efficiency; PER replay; ensemble uncertainty for position sizing | — Pending |
| Market-implied EPS vs. analyst consensus | Removes analyst anchoring bias; focuses on what market actually prices in | — Pending |
| Completion portfolio (~23% passive sleeve) | Neutralizes unintended factor tilts from PEAD strategy (growth/high-beta skew) | — Pending |
| Transformer pre-training frozen in v1.0 | Reduces training complexity; unfreeze in v2.0 with low LR | — Pending |
| Railway.app over AWS/GCP | Simpler ops, auto-deploy, ~$30/mo total vs. 10x for managed cloud | — Pending |
| Docker Compose for local dev | 6 services, consistent env; Railway uses same service definitions | — Pending |

## Evolution

This document evolves at phase transitions and milestone boundaries.

**After each phase transition** (via `/gsd-transition`):
1. Requirements invalidated? → Move to Out of Scope with reason
2. Requirements validated? → Move to Validated with phase reference
3. New requirements emerged? → Add to Active
4. Decisions to log? → Add to Key Decisions
5. "What This Is" still accurate? → Update if drifted

**After each milestone** (via `/gsd-complete-milestone`):
1. Full review of all sections
2. Core Value check — still the right priority?
3. Audit Out of Scope — reasons still valid?
4. Update Context with current state

---
*Last updated: 2026-05-02 after initialization*
